import aiohttp
import asyncio
import websockets
import json
import logging
import traceback
from collections import defaultdict

from typing import Any, Awaitable, DefaultDict, Dict, Iterable, List, Optional, Type

from ._rules import SlackRule, SlackID


log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


class SlackBot:
    def __init__(
        self,
        token: str,
        rules: Optional[List[Type[SlackRule]]] = None,
        report_to_user: Optional[str] = None,
    ) -> None:
        self.token: str = token
        self.report_to_user = report_to_user

        self.me: SlackID = SlackID("")
        self.id_to_user: Dict[SlackID, str] = {}
        self.user_to_id: Dict[str, SlackID] = {}
        self.id_to_channel: Dict[SlackID, str] = {}
        self.channel_to_id: Dict[str, SlackID] = {}

        rules_to_load = rules if rules is not None else SlackRule.all_rules()
        self.rules: List[SlackRule] = [rule(self) for rule in rules_to_load]

        self.session: aiohttp.ClientSession = aiohttp.ClientSession()

    def get_readable_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        event = dict(event)
        event["channel_name"] = self.id_to_channel.get(SlackID(event.get("channel", "")))
        event["user_name"] = self.id_to_user.get(SlackID(event.get("user", "")))
        return event

    async def log_and_report(self, message: str, level: int = logging.INFO) -> None:
        """Logs messages and reports them to the user."""
        log.log(level, message)
        if self.report_to_user:
            await self.api_call(
                method="chat.postMessage", channel=self.report_to_user, text=message
            )

    async def _handle_futures(
        self, futures: Iterable[Awaitable[Any]], event: Optional[Dict[str, Any]] = None
    ) -> None:
        """Awaits futures with timeout and handles any exceptions they may raise."""
        done, pending = await asyncio.wait(futures, timeout=20)
        if event:
            event = self.get_readable_event(event)
        for fut in pending:
            fut.cancel()
            await self.log_and_report(f"Timeout: On event `{event}`", level=logging.ERROR)
        for fut in done:
            try:
                await fut
            except Exception as e:
                await self.log_and_report(
                    f"Error: {e}\nOn event `{event}`\n```{traceback.format_exc()}```",
                    level=logging.ERROR,
                )

    async def api_call(self, **data: Any) -> Dict[Any, Any]:
        method = data.pop("method")
        data["token"] = self.token
        async with self.session.post(f"https://slack.com/api/{method}", data=data) as response:
            return await response.json()

    async def paginated_api_call(self, collect_key: str, **data: Any) -> Dict[Any, Any]:
        data["limit"] = 300
        response = await self.api_call(**data)
        ret = response[collect_key]
        next_cursor = response.get("response_metadata", {}).get("next_cursor")
        while next_cursor:
            response = await self.api_call(cursor=next_cursor, **data)
            ret.extend(response[collect_key])
            next_cursor = response.get("response_metadata", {}).get("next_cursor")
        return ret

    async def run(self) -> None:
        while True:
            try:
                response = await self.api_call(method="rtm.connect")
                if not response["ok"]:
                    return
                async with websockets.connect(response["url"]) as ws:
                    self.me = response["self"]["id"]
                    await asyncio.gather(self.load_user_map(), self.load_channel_map())
                    await self._handle_futures([rule.load() for rule in self.rules])
                    while True:
                        try:
                            message = await asyncio.wait_for(ws.recv(), timeout=20)
                        except asyncio.TimeoutError:
                            await asyncio.wait_for(ws.ping(), timeout=10)
                        else:
                            event = json.loads(message)
                            asyncio.ensure_future(self._process_event(event))
            except websockets.ConnectionClosed:
                pass

    async def _process_event(self, event_dict: Dict[str, Any]) -> None:
        event: DefaultDict[str, Any] = defaultdict(lambda: None, event_dict)
        if event["user"] == self.me:  # ignore events caused by me
            return

        if event["type"] == "message" and event["channel"] and event["channel"].startswith("D"):
            log.info(f"Direct message: {self.get_readable_event(event)}")

        async def _react_to_rule(rule: SlackRule) -> None:
            responses = await rule.react(event)
            if responses:
                log.info(f"Rule {rule} is responding to an event.")
            for response in responses:
                await self.api_call(**response)

        await self._handle_futures([_react_to_rule(rule) for rule in self.rules], event=event)

    async def load_user_map(self) -> None:
        users = await self.paginated_api_call("members", method="users.list")
        self.id_to_user = {u["id"]: u["name"] for u in users}
        self.user_to_id = {u["name"]: u["id"] for u in users}

    async def load_channel_map(self) -> None:
        channels = await self.paginated_api_call(
            "channels", method="conversations.list", types="public_channel,private_channel"
        )
        self.id_to_channel = {c["id"]: c["name"] for c in channels}
        self.channel_to_id = {c["name"]: c["id"] for c in channels}

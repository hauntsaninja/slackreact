import aiohttp
import re

from typing import (
    Any,
    DefaultDict,
    Dict,
    Iterable,
    Iterator,
    Match,
    NewType,
    Optional,
    Pattern,
    Set,
    Type,
    Union,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from ._bot import SlackBot  # noqlint  # used in an annotation

EventT = DefaultDict[str, Any]
SlackID = NewType("SlackID", str)

slack_rules: Set[Type["SlackRule"]] = set()


class SlackRule:
    def __init_subclass__(cls, abstract: bool = False) -> None:
        if not abstract:
            slack_rules.add(cls)

    @classmethod
    def all_rules(cls) -> Iterator[Type["SlackRule"]]:
        return iter(slack_rules)

    def __init__(self, bot: "SlackBot") -> None:
        self.bot = bot

    async def load(self) -> None:
        """Override to perform initialisation."""
        pass

    async def get_applicable_channels(self) -> Iterable[str]:
        """Returns a list of channel names to match."""
        raise NotImplementedError

    async def should_respond_to_channel(self, channel_id: SlackID) -> bool:
        """Override to get more control over channel matching."""
        channel_name = self.bot.id_to_channel.get(channel_id)
        if channel_name is None:
            return False
        return channel_name in await self.get_applicable_channels()

    async def should_respond_to_message(self, message: EventT) -> bool:
        """Returns whether or not to match the given message."""
        raise NotImplementedError

    async def should_respond_to_event(self, event: EventT) -> bool:
        """Override to get more control over event matching."""
        if event["type"] != "message":
            return False
        if not await self.should_respond_to_channel(event["channel"]):
            return False
        if event["text"] is None:
            event["text"] = ""
        return await self.should_respond_to_message(event)

    async def get_response_text(self, event: EventT) -> Union[str, Iterable[str]]:
        """Returns a string to respond on message match."""
        raise NotImplementedError

    async def respond(self, event: EventT) -> Iterable[Dict[str, Any]]:
        """Override to get more control over responses."""
        responses = await self.get_response_text(event)
        if isinstance(responses, str):
            responses = [responses]
        message = {"method": "chat.postMessage", "channel": event["channel"], "as_user": True}
        if event["thread_ts"] is not None:
            message["thread_ts"] = event["thread_ts"]
        return [dict(message, text=response) for response in responses]

    async def react(self, event: EventT) -> Iterable[Dict[str, Any]]:
        """Entry point for a rule. Override to get complete control over reaction."""
        if await self.should_respond_to_event(event):
            return await self.respond(event)
        return []


class MessageContainsRule(SlackRule, abstract=True):
    async def get_query_strings(self) -> Iterable[str]:
        """Returns a list of strings to match against the message."""
        raise NotImplementedError

    async def should_respond_to_message(self, message: EventT) -> bool:
        return any(q in message["text"].lower() for q in await self.get_query_strings())


class SnippetOrMessageContainsRule(MessageContainsRule, abstract=True):
    async def should_respond_to_message(self, message: EventT) -> bool:
        if await super().should_respond_to_message(message):
            return True
        if message["subtype"] != "file_share" or message["file"]["mode"] != "snippet":
            return False
        url = message["file"]["url_private"]
        headers = {"Authorization": f"Bearer {self.bot.token}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as resp:
                file_contents = await resp.text()
        return any(q in file_contents.lower() for q in await self.get_query_strings())


class MessageMatchesRegexRule(SlackRule, abstract=True):
    regex: Pattern[str] = NotImplemented

    async def get_regex(self) -> Pattern[str]:
        """Returns a regex to match against the message."""
        return self.regex

    async def get_regex_match(self, message: EventT) -> Optional[Match[str]]:
        """Returns a match object for the message."""
        return re.search(await self.get_regex(), message["text"])

    async def should_respond_to_message(self, message: EventT) -> bool:
        return bool(await self.get_regex_match(message))

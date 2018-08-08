import asyncio
import random
import re
import time
import slackreact as sr


class AreYouListening(sr.MessageContainsRule):
    """Check if the bot is listening.

    Examples:
    `are you there?`
    `robots of the world, are you listening?`

    """

    async def get_applicable_channels(self):
        return ["random"]

    async def get_query_strings(self):
        return ["are you there", "are you listening"]

    async def get_response_text(self, event):
        return "Yes. You can't see me, but I'm right behind you."


class DieRoll(sr.MessageMatchesRegexRule):
    """Rolls dice for you.

    Examples:
    `can i get a d3?`
    `10d6 drop lowest`

    """

    regex = re.compile(r"\b(\d*)d(\d+)\b")

    async def should_respond_to_channel(self, channel_id):
        return True

    async def get_response_text(self, event):
        regex_match = await self.get_regex_match(event)
        A = int(regex_match.group(1) or "1")
        X = int(regex_match.group(2))
        roll = sorted(random.randrange(X) + 1 for _ in range(A))
        if "drop lowest" in event["text"]:
            roll = roll[1:]
        if "drop highest" in event["text"]:
            roll = roll[:-1]
        return f"Sum of {sum(roll)} from rolling: " + ", ".join(map(str, roll))


class LoveMe(sr.MessageContainsRule):
    """Gives you some love (for five minutes).

    Examples:
    `does anyone love me :(`

    """

    async def load(self):
        self.needy = {}

    async def should_respond_to_channel(self, channel_id):
        return channel_id.startswith("D")  # only responds to DMs

    async def get_query_strings(self):
        return ["love me"]

    async def should_respond_to_message(self, message):
        if await super().should_respond_to_message(message):
            self.needy[message["user"]] = float(message["ts"])
        cutoff = time.time() - 5 * 60
        self.needy = {k: v for k, v in self.needy.items() if v > cutoff}
        return message["user"] in self.needy

    async def respond(self, event):
        return [
            {
                "method": "reactions.add",
                "name": "heart",
                "channel": event["channel"],
                "timestamp": event["ts"],
                "as_user": True,
            }
        ]


class Email(sr.MessageContainsRule):
    """What is the email of the tagged person?

    Examples:
    `what is @simba's email`

    """

    async def should_respond_to_channel(self, channel_id):
        return True

    async def get_query_strings(self):
        return ["email"]

    async def get_response_text(self, event):
        match = re.search("<@(U\w+)>", event["text"])
        if not match:
            return "You have to @tag the person" if event["channel"].startswith("D") else []
        user = match.group(1)
        if user == self.bot.me:
            return "I hope you'll excuse me, but I am a bot who values my privacy."
        user_info = await self.bot.api_call(method="users.info", user=user)
        return user_info.get("user", {}).get("profile", {}).get("email", "No email found :(")


def run(time=None):
    """Runs the bot for time seconds, or forever if None."""
    TOKEN = "insert your token here; get one at {team}.slack.com/apps/manage/custom-integrations"
    bot = sr.SlackBot(TOKEN)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(asyncio.wait_for(bot.run(), time))
    except asyncio.TimeoutError:
        pass
    loop.close()

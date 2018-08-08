Slackreact

Slackreact allows you to easily automatically respond to messages on Slack.
See `examples.py` for examples! Regexes are a cinch; the limit is anything that you can do with code.

All you have to do to set this up is supply a token for your Slack workspace. Under the hood, Slackreact uses a combination of the Web and RTM APIs. While it's running, it will listen in on any channel that the bot user is present in and selectively respond based on the rules you give it.

Requires Python 3.6 because everything is async and spiffy and type-checked and because I like f-strings.

import setuptools

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="slackreact",
    version="0.1.1",
    author="hauntsaninja",
    author_email="hauntsaninja@gmail.com",
    description="A framework to react and respond to messages on Slack.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/hauntsaninja/slackreact",
    packages=["slackreact"],
    classifiers=[
        "Programming Language :: Python :: 3.6",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Intended Audience :: Developers",
    ],
    keywords="slack bot slackbot regex",
    install_requires=["aiohttp", "websockets"],
    python_requires=">=3.6",
)

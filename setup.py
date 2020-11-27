from setuptools import find_packages, setup

setup(
    name="sportsref",
    version="0.12.0",
    description="Scraping data from sports-reference.com and related sites",
    url="https://github.com/mdgoldberg/sportsref",
    author="Matt Goldberg",
    author_email="matt.goldberg7@gmail.com",
    packages=find_packages(),
    install_requires=[
        "appdirs",
        "boltons",
        "mementos",
        "numexpr",
        "numpy",
        "pandas",
        "pyquery",
        "requests",
    ],
)

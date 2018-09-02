from setuptools import setup, find_packages

setup(name='sportsref',
      version='0.10.0',
      description='Scraping data from sports-reference.com and related sites',
      url='https://github.com/mdgoldberg/sportsref',
      author='Matt Goldberg',
      author_email='matt.goldberg7@gmail.com',
      packages=find_packages(),
      install_requires=[
          'appdirs',
          'boltons',
          'future',
          'mementos',
          'numexpr',
          'numpy',
          'pandas',
          'pyquery',
          'requests',
          'scipy',
      ]
      )

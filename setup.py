from setuptools import setup, find_packages

print 'Packages found: {}'.format(find_packages())

setup(name='pfr',
      version='0.1',
      description='Scraping data from pro-football-reference.com',
      url='https://github.com/mdgoldberg/pfr',
      author='Matt Goldberg',
      author_email='mgoldberg@college.harvard.edu',
      packages=find_packages()
      )

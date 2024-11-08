# setup.py
from setuptools import setup, find_packages

def read_requirements()->str:
    with open('requirements.txt', 'r') as f:
        return f.read().splitlines()

setup(
    name='amazon_product_search',
    version='0.1',
    packages=find_packages(),
    description='A library to search products on amazon without using pa Api',
    author='Manojpanda',
    author_email='manojpandawork@gmail.com',
    url='https://github.com/ManojPanda3/amazon-product-search',
    install_requires=read_requirements(),
)

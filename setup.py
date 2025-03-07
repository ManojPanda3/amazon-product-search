# setup.py
from setuptools import setup, find_packages


def read_requirements():
    return ["beautifulsoup4==4.12.3", "requests==2.32.3", "lxml==5.3.1"]


def read_long_description():
    with open("README.md", "r", encoding="utf-8") as f:
        return f.read()


setup(
    name="amazon_product_search_v2",  # This is the name used for `pip install`
    version="0.1.1",  # Use semantic versioning (major.minor.patch)
    packages=find_packages(exclude=["tests*"]),
    description="A library to search products on Amazon without using the PA API",
    long_description=read_long_description(),
    long_description_content_type="text/markdown",
    author="Manojpanda",
    author_email="manojpandawork@gmail.com",
    url="https://github.com/ManojPanda3/amazon-product-search",
    install_requires=read_requirements(),
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Programming Language :: Python :: 3.13",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    keywords="amazon product search scraping web scraping",
    python_requires=">=3.7",
)

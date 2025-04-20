from setuptools import setup, find_packages

with open("README.md", "r") as f:
    long_description = f.read()

setup(
    name="somfy-rts-hub-LukasHirsch99",
    version="0.0.1",
    author="Lukas Hirsch",
    author_email="lukas.stag@gmail.com",
    description="A small package to talk to somfy-rts-esp devices.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/LukasHirsch99/somfy-rts-hub",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ]
)

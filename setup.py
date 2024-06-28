from setuptools import setup

with open("README.md", "r", encoding="utf8") as fh:
    long_description = fh.read()

setup(
    name="addon-system",
    version="1.2.12",
    packages=[
        "addon_system",
        "addon_system.addon",
        "addon_system.system",
        "addon_system.libraries",
    ],
    entry_points={
        "console_scripts": [
            "make-addon = addon_system.make_addon:main",
            "addon = addon_system.make_addon:main",  # backwards compatibility
        ]
    },
    url="https://github.com/kuyugama/addon-system",
    license="GNU GPVv3",
    author="KuyuGama",
    author_email="mail.kuyugama@gmail.com",
    description="The AddonSystem library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=["Programming Language :: Python :: 3"],
    python_requires=">=3.9",
    extras_require={"baked": ["pybaked==0.0.12"]},
)

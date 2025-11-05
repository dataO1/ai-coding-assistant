from setuptools import setup, find_packages

setup(
    name="ag2-agent-network",
    version="0.1.0",
    description="AG2 Parallel Agent Network for Multi-Agent Development",
    author="Your Organization",
    license="MIT",
    packages=find_packages(),
    python_requires=">=3.11",
    install_requires=[
        "ag2>=0.9.0",
        "openai>=1.0.0",
        "chromadb>=0.5.0",
        "pydantic>=2.0.0",
        "python-dotenv>=1.0.0",
        "pyyaml>=6.0",
    ],
    entry_points={
        "console_scripts": [
            "agent-network=main:main",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.11",
    ],
)

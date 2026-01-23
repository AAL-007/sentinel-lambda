from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="sentinel-lambda",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Enterprise AI Safety Supervision Framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/sentinel-lambda",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "Intended Audience :: Developers",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.9",
    install_requires=[
        "fastapi>=0.104.0",
        "pydantic>=2.4.0",
        "streamlit>=1.28.0",
        "pandas>=2.0.0",
        "plotly>=5.18.0",
        "redis>=5.0.0",
        "celery>=5.3.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.0",
            "pytest-cov>=4.1.0",
            "black>=23.0.0",
            "flake8>=6.0.0",
            "mypy>=1.6.0",
            "pre-commit>=3.5.0",
        ],
        "ml": [
            "openai>=1.0.0",
            "anthropic>=0.7.0",
            "sentence-transformers>=2.2.0",
            "scikit-learn>=1.3.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "sentinel-api=src.api.server:main",
            "sentinel-dashboard=src.dashboard.app:main",
        ],
    },
    include_package_data=True,
    package_data={
        "sentinel_lambda": ["data/rules/.json", "data/benchmarks/.json"],
    },
)

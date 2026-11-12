# AI Video Editor --- Local Setup Guide

This guide explains how to install the tools, download the AI Video
Editor source code, configure its dependencies, and run it on a Windows
computer.

The project uses **Python**, **Streamlit**, and video-processing
libraries. The repository also contains a `uv.lock` file, so this guide
uses **uv** to install the exact dependency versions recorded by the
project.

> **Before you begin:** Replace `<YOUR_GITHUB_REPOSITORY_URL>` in the
> cloning command with the actual HTTPS or SSH clone URL of this
> repository. The repository URL was not available when this guide was
> prepared.

------------------------------------------------------------------------

## 1. Install Python

1.  Open the official Python downloads page: **python.org/downloads**.
2.  Download **Python 3.12.x for Windows (64-bit)**.
3.  Run the installer.
4.  On the first installer screen, enable **Add python.exe to PATH**.
5.  Select **Install Now** and allow the installation to finish.

### Verify Python

Open **PowerShell** and run:

``` powershell
python --version
```

You should see Python 3.12.x.

Also verify that `pip` is available:

``` powershell
python -m pip --version
```

If `python` is not recognized, reopen PowerShell. If it is still
unavailable, rerun the Python installer and enable **Add python.exe to
PATH**.

------------------------------------------------------------------------

## 2. Install Git

Git is required to clone the project repository.

1.  Open **git-scm.com/download/win**.
2.  Download and install Git for Windows.
3.  The default installation options are suitable for this project.

Verify the installation in PowerShell:

``` powershell
git --version
```

------------------------------------------------------------------------

## 3. Install uv

The project includes `pyproject.toml` and `uv.lock`. Use **uv** to
install the dependencies consistently with the lockfile.

In PowerShell, run:

``` powershell
python -m pip install --upgrade pip
python -m pip install uv
```

Verify:

``` powershell
uv --version
```

------------------------------------------------------------------------

## 4. Clone the GitHub repository

Choose a location for your projects. For example, to use a `Projects`
folder on your D: drive:

``` powershell
New-Item -ItemType Directory -Force -Path "D:\Projects"
Set-Location "D:\Projects"
```

Clone the repository:

``` powershell
git clone <YOUR_GITHUB_REPOSITORY_URL>
```

Move into the cloned project folder. Replace `videoeditor` if the
repository was cloned into a differently named folder:

``` powershell
Set-Location "D:\Projects\videoeditor"
```

Check that you are in the project root:

``` powershell
Get-ChildItem
```

You should see the project's files, including its dependency
configuration (`pyproject.toml` and `uv.lock`) and Streamlit entry-point
file (`main.py`).

------------------------------------------------------------------------

## 5. Install the project dependencies

From the project root, run:

``` powershell
uv sync
```

This creates a project virtual environment (normally `.venv`) and
installs the dependencies recorded in `uv.lock`.

Wait for the command to complete. Do not install packages individually
unless the project reports a missing dependency and the project
maintainers have confirmed how it should be added.

### Verify the environment

Run:

``` powershell
uv run python --version
```

You can also check that the key application packages import correctly:

``` powershell
uv run python -c "import streamlit, cv2; print('Core imports successful')"
```

If this check reports a missing module, confirm that `uv sync` completed
successfully and that you are running the command from the project root.

------------------------------------------------------------------------

## 6. Install or verify FFmpeg

The application uses video-processing functionality. Some workflows may
require an FFmpeg executable to be available on the system.

First, check whether FFmpeg is already installed:

``` powershell
ffmpeg -version
```

If PowerShell reports that `ffmpeg` is not recognized, install an FFmpeg
Windows build using a trusted distribution, then reopen PowerShell and
run the verification command again.

If the application uses the bundled `imageio-ffmpeg` executable for a
particular operation, that may provide FFmpeg for that operation; it
does not necessarily replace a system FFmpeg installation required by
other commands.

------------------------------------------------------------------------

## 7. Configure API keys and secrets (if required)

Some AI features may require API credentials. **Only configure the keys
for services that are actually enabled and referenced by the current
application code.** Do not assume that every feature shown in the
interface is active.

1.  Check the repository for `.env.example`, README instructions, or the
    configuration module to identify the exact environment-variable
    names.

2.  If a `.env.example` file exists, copy it to `.env`:

    ``` powershell
    Copy-Item .env.example .env
    ```

3.  Open `.env` in a text editor and enter your own API keys using the
    exact variable names specified by the project. For example, the
    format may look like this:

    ``` dotenv
    SERVICE_API_KEY=your_actual_key_here
    ```

4.  Save the file.

**Security rules:** - Never share your API keys or commit them to
GitHub. - Keep `.env` out of version control. The repository's
`.gitignore` should exclude it. - Do not put quotation marks around
values unless the project's configuration instructions require them. -
If no API key is needed for the feature you are testing, you can skip
this section.

------------------------------------------------------------------------

## 8. Run the application

From the project root, start Streamlit with:

``` powershell
uv run streamlit run main.py
```

Streamlit should print a local address, usually:

``` text
http://localhost:8501
```

Open that address in your browser.

To stop the application, return to PowerShell and press:

``` text
Ctrl + C
```

------------------------------------------------------------------------

## 9. Start the application next time

After the initial setup, you do not need to clone the repository or
reinstall dependencies every time.

1.  Open PowerShell.

2.  Navigate to the project folder:

    ``` powershell
    Set-Location "D:\Projects\videoeditor"
    ```

3.  Start the application:

    ``` powershell
    uv run streamlit run main.py
    ```

------------------------------------------------------------------------

## 10. Update the project

To download the latest committed changes from the repository:

``` powershell
git pull
```

If the dependency files (`pyproject.toml` or `uv.lock`) have changed,
synchronize the environment again:

``` powershell
uv sync
```

Then restart the application:

``` powershell
uv run streamlit run main.py
```

------------------------------------------------------------------------

## Troubleshooting

### `python` is not recognized

-   Reopen PowerShell after installing Python.
-   Confirm that **Add python.exe to PATH** was enabled during
    installation.
-   Run the Python installer again and choose **Modify** if necessary.

### `git` is not recognized

-   Confirm Git for Windows is installed.
-   Reopen PowerShell so the updated PATH is loaded.

### `uv` is not recognized

Run:

``` powershell
python -m pip install --upgrade uv
```

Then reopen PowerShell and verify with `uv --version`.

### A Python module is missing

Run this from the project root:

``` powershell
uv sync
```

If the error remains, note the exact missing module and full traceback.
Do not randomly install similarly named packages: Python import names
and package names are not always identical.

### `ffmpeg` is not recognized

Install FFmpeg, ensure its executable directory is on the Windows PATH,
reopen PowerShell, and check:

``` powershell
ffmpeg -version
```

### An API authentication error appears

-   Verify that the required API key is valid and active.
-   Confirm that the variable name in `.env` exactly matches the name
    read by the application.
-   Restart Streamlit after changing `.env`.
-   Never paste API keys into issue reports or public screenshots.

### Port 8501 is already in use

Start Streamlit on another port:

``` powershell
uv run streamlit run main.py --server.port 8502
```

Then open `http://localhost:8502`.

------------------------------------------------------------------------

## Setup checklist

-   [ ] Python 3.12 installed and available in PowerShell.
-   [ ] Git installed and available in PowerShell.
-   [ ] uv installed and available in PowerShell.
-   [ ] Repository cloned to the computer.
-   [ ] PowerShell opened in the project root.
-   [ ] `uv sync` completed successfully.
-   [ ] FFmpeg verified if required by the installed workflows.
-   [ ] Required API keys configured locally, if applicable.
-   [ ] Streamlit started successfully with
    `uv run streamlit run main.py`.

**You are ready to use the AI Video Editor locally.**

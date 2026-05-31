# CI/CD Deployment Setup Guide — Lexie (FastAPI on EC2)

## Overview

This guide sets up automated deployment via GitHub Actions:
- Every push to `main` runs the full pytest suite
- If all tests pass, the code is deployed to EC2 automatically
- The `.env` file on the server is never touched

---

## Step 1 — Generate the SSH deploy key (on your Windows machine)

Open Command Prompt and run:

```bash
mkdir %USERPROFILE%\.ssh
ssh-keygen -t ed25519 -C "github-actions-deploy" -f "%USERPROFILE%\.ssh\lexie_deploy_key" -N ""
```

> The `-N ""` sets an empty passphrase — this is intentional and required so
> GitHub Actions can use the key without a human typing a passphrase.

This creates two files:
- `C:\Users\<you>\.ssh\lexie_deploy_key` — private key (goes into GitHub Secret)
- `C:\Users\<you>\.ssh\lexie_deploy_key.pub` — public key (goes onto the EC2 server)

---

## Step 2 — Add the public key to your EC2 instance

Since you are using **AWS EC2 Instance Connect** (browser-based terminal), you
cannot transfer files directly. Use the copy-paste method instead.

**On your Windows machine**, print the public key:

```bash
type "C:\Users\Jayesh Motwani\.ssh\lexie_deploy_key.pub"
```

Copy the entire output — it is one long line starting with `ssh-ed25519`.

**In your EC2 Instance Connect terminal**, run:

```bash
# Create .ssh directory and authorized_keys if they don't exist yet
mkdir -p ~/.ssh
touch ~/.ssh/authorized_keys
chmod 700 ~/.ssh
chmod 600 ~/.ssh/authorized_keys

# Paste your public key (replace the placeholder with your actual key)
echo "ssh-ed25519 AAAA....paste the whole line here" >> ~/.ssh/authorized_keys
```

---

## Step 3 — Allow passwordless sudo for the systemd restart

On the EC2 Instance Connect terminal, run:

```bash
echo "ubuntu ALL=(ALL) NOPASSWD: /bin/systemctl restart fastapi.service" \
  | sudo tee /etc/sudoers.d/github-actions-fastapi
sudo chmod 440 /etc/sudoers.d/github-actions-fastapi

# Verify the syntax is valid before logging out
sudo visudo -c
```

This scopes the passwordless sudo to only the one command GitHub Actions needs —
not blanket sudo access.

---

## Step 4 — Set up the repo and virtual environment on EC2

If this is your first deployment, run these once on the EC2 terminal:

```bash
cd /home/ubuntu
git clone <your-repo-url> language-tutor
cd language-tutor
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Then copy your `.env` file to the server. Because `.env` is in `.gitignore`,
git never touches it — it will survive every future deployment unchanged.

The easiest way from Windows is via SCP in Command Prompt:

```bash
scp -i "C:\Users\Jayesh Motwani\.ssh\lexie_deploy_key" .env ubuntu@<your-ec2-ip>:/home/ubuntu/language-tutor/.env
```

Or if you only have EC2 Instance Connect access, create the `.env` manually:

```bash
nano /home/ubuntu/language-tutor/.env
# Paste your env var contents, then Ctrl+O to save, Ctrl+X to exit
```

---

## Step 5 — Fix file permissions

Ensure the `ubuntu` user owns the entire project directory:

```bash
sudo chown -R ubuntu:ubuntu /home/ubuntu/language-tutor
chmod 600 /home/ubuntu/language-tutor/.env
```

---

## Step 6 — Confirm your systemd service

The workflow restarts `fastapi.service` by name. If you haven't created it yet,
create `/etc/systemd/system/fastapi.service`:

```bash
sudo nano /etc/systemd/system/fastapi.service
```

Paste this content:

```ini
[Unit]
Description=Lexie FastAPI Service
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/home/ubuntu/language-tutor
EnvironmentFile=/home/ubuntu/language-tutor/.env
ExecStart=/home/ubuntu/language-tutor/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable fastapi.service
sudo systemctl start fastapi.service

# Verify it's running
sudo systemctl status fastapi.service
```

---

## Step 7 — Add GitHub Secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

| Secret name | What it contains | How to get it |
|---|---|---|
| `EC2_HOST` | Your EC2 public IP or DNS, e.g. `54.123.45.67` | EC2 console → instance details |
| `EC2_SSH_PRIVATE_KEY` | Full contents of `lexie_deploy_key` (private key) including the header and footer lines | Run `type "C:\Users\Jayesh Motwani\.ssh\lexie_deploy_key"` on Windows and copy everything |

> Only these two secrets are needed. All app secrets (`OPENAI_API_KEY`, `JWT_SECRET_KEY`,
> `DATABASE_URL`, etc.) live in `.env` on the server and never pass through GitHub.

---

## Step 8 — Add the deploy workflow to your repo

Place the following file at `.github/workflows/deploy.yml` in your project:

```yaml
name: Test & Deploy

on:
  push:
    branches: [ "main" ]

permissions:
  contents: read

jobs:
  test:
    name: Run test suite
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Cache pip packages
        uses: actions/cache@v4
        with:
          path: ~/.cache/pip
          key: ${{ runner.os }}-pip-${{ hashFiles('requirements.txt') }}
          restore-keys: |
            ${{ runner.os }}-pip-

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run pytest
        run: pytest tests/ -v

  deploy:
    name: Deploy to EC2
    runs-on: ubuntu-latest
    needs: test

    steps:
      - name: Deploy via SSH
        uses: appleboy/ssh-action@v1.0.3
        with:
          host:     ${{ secrets.EC2_HOST }}
          username: ubuntu
          key:      ${{ secrets.EC2_SSH_PRIVATE_KEY }}
          port:     22
          script: |
            set -e
            cd /home/ubuntu/language-tutor
            git fetch origin main
            git reset --hard origin/main
            source venv/bin/activate
            pip install --quiet -r requirements.txt
            sudo systemctl restart fastapi.service
            echo "Deployment complete."
```

---

## How it all fits together

1. You push to `main`
2. GitHub Actions runs all 32 pytest tests in a clean environment
3. If any test fails, deployment is blocked — nothing reaches the server
4. If all tests pass, Actions SSHes into EC2, pulls the latest code, updates
   dependencies, and restarts the service
5. Your `.env` file on the server is never read, written, or deleted at any point

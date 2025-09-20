On Linux you can configure Codex CLI to stop asking for command approvals by combining API key auth with full-auto mode.

Steps

1) Export your API key
Add this to your shell profile (~/.bashrc or ~/.zshrc):
  export OPENAI_API_KEY="sk-yourapikey"
Then reload:
  source ~/.bashrc

2) Set up config file
Create or edit ~/.codex/config.toml:
  preferred_auth_method = "apikey"
  approval_mode = "full-auto"

  [projects."/home/youruser/yourrepo"]
  trust_level = "trusted"
  sandbox_mode = "workspace-write"

Replace /home/youruser/yourrepo with the absolute path to your project.

3) Run Codex
Now you can run:
  codex
It will use your API key, skip per-command authorization, and run inside the trusted repo sandbox.

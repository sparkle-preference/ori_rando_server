"""Mock game clients for integration scenarios. Not part of the shipped server.

Run scenarios with:  .venv312\\Scripts\\python.exe -m mockclient.run <scenario>
Requires the datastore_test emulator (docker compose up -d datastore_test);
the runner starts and owns its own flask on a scenario port.
"""

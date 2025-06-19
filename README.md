# Ori DE Randomizer Server

Repository for the [Ori DE Randomizer](https://orirando.com) server.

## Getting Started

This repository contains the UI and backend code for the Ori DE randomizer website. New players: check out the [quickstart page](https://orirando.com/quickstart). Help for the various seed generation settings can be found on by mousing over the relevant UI elements.

## Key Features
* Seed Generator - Generates randomizer.dat seeds
* Logic Helper - Simple interface to determine in-logic pickups based on current skills and resources. Manual
* Online Tracking Map - Web-based live tracker showing current available pickups on the world map by updating to this server 
* Plandomizer Builder - Tool to allow players to design and share custom logic seeds
* Bingo - Provides multiplayer bingo tracking.

## Development 
We welcome your contributions!
This server is a hybrid [Flask](https://flask.palletsprojects.com/) and [React](https://react.dev/) app, and runs on [Google App Engine](https://cloud.google.com/appengine?hl=en).

### Prerequisites
#### Python
Make sure you have [Python 3.12](https://www.python.org/downloads/). We recommend [pyenv](https://github.com/pyenv/pyenv) to manage your python installations.

#### Javascript
Make sure you have [Node 22 or higher](https://nodejs.org/en/download).

#### Java
You'll also need Java 8 or higher; we recommend [Temurin 21](https://adoptium.net/temurin/releases/?os=any&arch=any&version=21).

#### Google Cloud SDK
Google cloud provides [official install instructions here](https://cloud.google.com/sdk/docs/install-sdk), but your package manager may have a pre-packaged version available via `google-cloud-sdk`. Please note that the `snap` install of the sdk is missing the App Engine extensions required for this use case.

### Building the frontend
The frontend is built as a standalone react application. To build the application for first launch 
```sh
cd map
npm install
npm run build
```

To start the react dev server, run
```sh
cd map # If you're not already in the directory
npm start
```

### Component install
Once installed, use the Google Cloud SDK CLI to install the Python App Engine and Cloud Datastore Emulator components.
```sh
gcloud components install app-engine-python cloud-datastore-emulator
```

If installed via `apt` run
```sh
sudo apt-get update && sudo apt-get install google-cloud-cli-app-engine-python google-cloud-cli-datastore-emulator
```

### Dev Server
Run the dev server with
```sh
./run_dev_server.sh
```
By default this uses port `8080` and binds to `127.0.0.1`; If you'd like to use a different port or bind you can set the `APP_PORT` and `APP_HOST` environment variables

```sh
APP_PORT="5432" APP_HOST="0.0.0.0" ./run_dev_server.sh
```

For additional help, you can contact me (Eiko) in the [Ori Randomizer Discord](https://orirando.com/discord)


## Related Projects 
* [OriDE Randomizer](https://github.com/sparkle-preference/OriDERandomizer)
* [OriDETracker](https://github.com/meldontaragon/OriDETracker)
* [Autosplitter for Ori DE](https://github.com/ShootMe/LiveSplit.OriDE)

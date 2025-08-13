# Ori DE Randomizer Server

Repository for the [Ori DE Randomizer](https://orirando.com) server.

## Getting Started

This repository contains the UI and backend code for the Ori DE randomizer website. New players: check out the [quickstart page](https://orirando.com/quickstart). Help for the various seed generation settings can be found on by mousing over the relevant UI elements.

## Key Features
* Seed Generator - Generates randomizer.dat seeds
* Logic Helper - Simple interface to determine in-logic pickups based on current skills and resources. Manual
* Online Tracking Map - Web-based live tracker showing current available pickups on the world map by updating to this server 
* Plandomizer Builder - Tool to allow players to design and share custom logic seeds
* Bingo - Provides multiplayer bingo tracking

## Development 
We welcome your contributions!
This server is a hybrid [Flask](https://flask.palletsprojects.com/) and [React](https://react.dev/) app, and runs on [Google Cloud Run](https://cloud.google.com/run).

### Prerequisites
#### Docker
You'll need a version of the [Docker Runtime](https://docs.docker.com/engine/), as well as a version of [Docker Compose](https://docs.docker.com/compose/).
You can get both by installing [Docker Desktop](https://docs.docker.com/desktop/), which is free for personal use.
### Dev Server
Run the dev server with
```sh
docker compose up
```
This will expose two services
- The server itself will begin serving at http://localhost:8080
- A Databse explorer will be available at http://localhost:8081

#### Other Dev Server Options
- `MEMCACHED_HOST`: Sets the hostname of the memcached service to use. Default `memcached`.
- `MEMCACHED_PORT`: Sets the port of the memcached service to use. Default `11211`.
- `GOOGLE_CLOUD_PROJECT`: Sets the name of the google cloud project to use with Datastore. Default `orirandov3`.
- `DATASTORE_EMULATOR_HOST`: Sets the location of the datastore emulator to use. Tries to use production Datastore if left empty. Default `datastore:8000`.
- `OIDC_ENABLED`: Enables or disables actual credential checking. Default `False`.
- `OIDC_TESTING_EMAIL`: Email of the mock account generated for testing. Default `testing@example.com`.
- `OIDC_TESTING_ID`: User ID of the mock account generated for testing. Default `123454321234543212345`.
- `WHITELIST_SECRET`: Secret used for races. Default `PLACEHOLDER_DEV_SECRET`
- `APP_SECRET_KEY`: Flask's secret key, used to save user login sessions. Default `INSECURE_DEV_SECRET_KEY`.
- `NO_WATCH_REACT_APP`: Don't watch for changes in the React App after initial build. If you'd like to not build the React app at all, avoid running the `react` service in `docker-compose.yml`.

For additional help, you can contact me (Eiko) in the [Ori Randomizer Discord](https://orirando.com/discord).


## Related Projects 
* [OriDE Randomizer](https://github.com/sparkle-preference/OriDERandomizer)
* [OriDETracker](https://github.com/meldontaragon/OriDETracker)
* [Autosplitter for Ori DE](https://github.com/ShootMe/LiveSplit.OriDE)

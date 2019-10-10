Ori DE Coop Server
==================

Repository for Ori DE [coop randomizer server](https://orirando.com) and [plando builder](https://orirando.com/plando/simple)!

## Getting Started

This repository contains the UI and backend code for the Ori DE randomizer.  For players, see the [Getting Started documentation](https://orirando.com). Detailed descriptions of the randomizer modes will be displayed on the side when the mode is selected from the pull down menu. Custom options and advanced setting help can be viewed by mousing over an option in the web browser.

## Key Features
* Seed Generator - Generates randomizer.dat seeds
* Logic Helper - Simple interface to determine in-logic pickups based on current skills and resources. Manual
* Online Tracking Map - Web-based live tracker showing current available pickups on the world map by updating to this server 
* Plandomizer - Tool to allow players to design and share custom logic seeds
* Bingo

### Web Tracking


## Development 
We welcome your contributions!
This server is build to work with the Google App Engine.

To develop locally, 
* Install the [Google App Engine SDK](https://cloud.google.com/sdk/docs/) for your OS.
* Clone [this repository](https://github.com/turntekGodhead/ori_rando_server.git)
* Setup the simulation environment by running:  
```
   ./dev_appserver.py .
```

First time setup can take a few minutes.  Be patient

See this link to the tutorial on getting started with the [App Engine SDK](http://webapp2.readthedocs.io/en/latest/tutorials/gettingstarted/)

## Related Projects 
* [OriDE Randomizer](https://github.com/sigmasin/OriDERandomizer)
* [OriDETracker](https://github.com/meldontaragon/OriDETracker)
* [Autosplitter for Ori DE](https://github.com/ShootMe/LiveSplit.OriDE)


# [direnv](https://direnv.net) integration for Sublime Text 3

This plugin adds support for direnv to Sublime Text 3.

## Prerequisites

This plugin needs direnv installed to work. Please refer [here](https://direnv.net/docs/installation.html) for installation instructions.

## Installation

You can install via [Sublime Package Control plugin](https://packagecontrol.io/installation):

* Press `(ctrl|cmd)+shift+p` to view the Command Palette in Sublime Text.
* Type the command Package Control: Install Package
* Type the name Direnv and choose it from the list.

## Usage

This plugin will automatically load a `.envrc` file to the environment if you allowed it to.

## Commands

In order to run a command press `(ctrl|cmd)+shift+p` to view the Command Palette. There type:

* `direnv allow` to allow and load the current .envrc
* `direnv deny` to deny and unload the current .envrc

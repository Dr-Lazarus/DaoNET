# Dao-net
## An application-layer protocol to bring order to P2P multiplayer games

Inspired by League of Legend's game clock synchronisation, this project aims to build an application-layer protocol that mitigates the propagation of erroneous game states due to network delay in a P2P, latency-averse multiplayer game by synchronising game clock.

This project was done for SUTD's 50.021: Networks module. The aim of the project is to propose a specific problem related to networks application, protocol or architecture.

## Project Structure
- Game
    - Clock
        - clock.py
        - delay.py
        - sync.py
    - Lobby
        - lobby.py
        - tracker.py
    - Models
        - player.py
    - Transport
        - packet.py
        - transport.py
- client.py
- thread_manager.py
- logs

## Features
The two main issues of a P2P game are network delay and game state consensus.


Thus, we have designed a two-pronged approach:

1. Latency Aware Propagation 
2. Frame Syncing




In addition, we have implemented a P2P version of musical chairs known as `QWERTYchairs` to test our solution.



## Project Architecture

![](https://i.imgur.com/hJ88Sdj.png)



## Getting Started
1. Git clone the repository
```
git clone https://github.com/rphly/dao-net.git
```

2. Open up the root directory and install the dependencies
```
pip install -r requirements.txt
```


## Running the Game
A minimum of two players are required to play the game.

1. On one machine, set up a host lobby with the commands:

a) MacOs
```
clear && sudo -E ./env/bin/python main.py -m host -ip <your_ip_address> -hp <port_number>
```
b) Windows
```
python main.py -m host -ip localhost -hp 9999
```
On a successful host startup, the host should see the message:
```
Starting host mode on port 9999.
```

Whenever another player has joined the lobby, the host should see:
```
Player registered: vital-boar
Current players: ['tough-hyena', 'vital-boar']
```



2. On another machine, enter the lobby as a player using:

a) MacOs
```
clear && sudo -E ./env/bin/python main.py -ip <host_ip_address> -hp <host_port_number> -pip <your_ip_address> -pp <port_number>
```
b) Windows
```
python main.py -ip <host_ip_address> -hp <host_port_number> -pip <your_ip_address> -pp <port_number>
```

On a successful player startup, the player should see the message:
```
Starting in player mode.
```

3. The host will be updated when players join the lobby:

```
Current players: ['tough-hyena']
Player registered: vital-boar
Current players: ['tough-hyena', 'vital-boar']
```

4. When there are sufficient players (more than 1), the host can start the game by pressing the`SPACEBAR` key.


```
All clients notified of game start.
Exiting lobby, entering game
```


## How to Play QWERTYchairs

### Selecting Seats
When synchronisation is done, the game will begin counting down. When the countdown finishes, the round will start and players will be prompted to "take a seat" by pressing on one of the keys "Q","W","E","R","T", or "Y".

```
|-------- ROUND 1 --------|
[PLAYING AS] vital-boar
[CURRENT PLAYERS] ['vital-boar', 'tough-hyena']
[AVAILABLE SEATS] {'Q': None}
[SYSTEM] GRAB A SEAT NOW !!!
```

If the player manages to successfully take that seat i.e. no one else has taken that seat before the player, he will see:

```
[ACTION] I HAVE PRESSED Q
[ACTION] I have sat down successfully!
[SEATS] {'Q': 'vital-boar'}
```

If the player has failed to take a seat, he will see:
```
[ACTION] I HAVE PRESSED Q
[ACTION] Failed to sit down, pick a new seat!
```

When another player has taken a seat, he will see a prompt:
```
[ACTION] vital-boar has sat down!
[SEATS] {'Q': 'vital-boar'}
```
### Determining the loser of the round
When the seats are filled, players will hold a vote to kick the player who has failed to find a seat on their records. When all votes are in, the player will be moved into a spectator state.

```
[VOTE] Voting to kick: tough-hyena
[SYSTEM] Received vote to kick tough-hyena

 ---- ALL VOTES IN ----
[KICKING LOSER] Kicking player: tough-hyena
```

### Round End
The game continues until there is one player left, after which the game will terminate.

```
---- Round has ended. Players left: ['vital-boar'] ----
[SYSTEM] Reducing number of chairs...
[SYSTEM] No more seats left, game over.

--- Congrats! You have won the game! ---

Hope you had fun!
```



## Visualising the Test Results for Frame Syncing
The results of the game will automatically be logged. These logs will be stored in the `./logs` folder, shift all the log files for relevant game to the `./logs_parse` folder. 

To see the test results for frame syncing in a chart, key in the command:

```
python visualizations.py
```

## Additional Resources
Project Report:
https://docs.google.com/document/d/1M1x-pMdd0eYDzquYMMAF3uyoVvAy0XSJtn3hpExUnaA/edit#

Final Presentation:
https://docs.google.com/presentation/d/1FkBAM7jufYnY1UtCDipZn64lYQgso2DqmwFn6kiv5KM/edit#slide=id.g22c0e6bf17b_0_629


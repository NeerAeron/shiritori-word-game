# Shiritori Word Game

## Video Demo:  <URL HERE>

## Description:

A terminal based implementation of the japanese word game shiritori and the atlas word game.with flexible implementation allowing for similar games to be created.

## Features:

- Two game modes: Shiritori and Atlas.
- Support for 1 - unlimited players
- Mutli-level computer opponent, mimics human play
- timer display for each turn
- Customizable game settings: dictionary, max word length, game duration, and input type.
- Flexible architecture for adding new game modes

## Game Rules:

- Players take turns to add words to a chain, with each word starting with the last letter of the previous word.
- Words must be at least 3 letters long
- No repetition of words is allowed
- Atlas:
    - Dictionaries: us states, world cities, countries
    - Time per input: 30 seconds
    - Game Ending: Player removed if no input given within time limit, game continues until 
                   one player remains
- Shiritori:
    - Dictionaries: english words
    - Time per input: Infinite
    - Game Ending: Score per word determined based on length and time taken,
                   game continues until one player reaches winning score (default: 100)


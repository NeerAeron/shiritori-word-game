"""
The `Game` class represents the main game logic for the Shiritori word game. 
It handles the setup of the game, including the number of players and the difficulty level, as well as the game loop and scoring.

The `Player` class represents a player in the game, with a name and a score.

The `Timer` class is responsible for managing the countdown timer and handling user input during each round of the game.
"""

import random
import string
import time
from pyfiglet import figlet_format
import sys
import threading
import readchar
from dataclasses import dataclass

@dataclass
class Player:
    name: str
    score: int = 0

    def __str__(self):
        return f'{self.name}: {self.score}'

    def change_score(self, n: int):
        self.score += n

    def __post_init__(self):
        self.name = self.name.title()

"""
    The `Game` class represents the main game logic for the Shiritori word game. 
    It handles the setup of the game, including the number of players and the difficulty level, as well as the game loop and scoring.
    
    The `run_game` method runs the main game loop, alternating between user and computer rounds until a player reaches the winning score. 
    The `run_round_user` and `run_round_computer` methods handle the logic for a single round of the game, including getting user input or choosing a word for the computer, and calculating the score.
    
    The `choose_word` method selects a valid word for the computer to play, based on the current difficulty level. 
    The `get_score` and `check_word` are used to calculate the score for a given word and check if a word is valid, respectively.
"""

class Shirotori:
    _WINNING_SCORE = 100
    _MIN_WORD_LEN  = 3
    _MAX_PLAYERS = 3

    # level: (min_word_length, max_word_length, average_word_length, standard_deviation)
    _DIFFICULTIES = {
            'easy': (_MIN_WORD_LEN, 6, 4.5, 0.8),
            'medium': (_MIN_WORD_LEN + 3, 11, 8, 1.3),
            'hard': (_MIN_WORD_LEN + 5, None, 12, 3),
            'impossible': (_MIN_WORD_LEN + 10, None, 18, 4)
    }

    # input type 1: score
    # input type 2: timed
    _GAME_TYPES = {
        'normal': {
            'dictionary': ['dictionaries/dictionary.txt', 'dictionaries/dictionary2.txt'],
            'countdown_time': 10,
            'input_type': 1
        },
        'atlas': {
            'dictionary': ['dictionaries/uscities.txt', 'dictionaries/usstates.txt', 
                           'dictionaries/countries.txt', 'dictionaries/worldcities.txt',
                           'dictionaries/continents.txt'],
            'countdown_time': 30,
            'input_type': 2
        },
    }

    def __init__(self, players: int = 1, difficulty: str = 'easy', game_type: str = 'normal', player1: str = 'Player 1'):
        self._players = self.set_players(players)
        self._difficulty = self.set_difficulty(difficulty)
        self._game_type = self.set_game_type(game_type)
        self._player_list = [Player(player1), Player('Computer')]
        self._round = 0
        self._used_words = set()    

    @staticmethod
    def title():
        return f'{figlet_format('Shiritori', font='chunky')}{figlet_format('By: Neer', font='small')}'

    def setup_players(self):
        while True:
            try:
                self._players = self.set_players(int(input(f'Number of players (1 - {self._MAX_PLAYERS}): ').strip()))  
                break              
            except ValueError:
                print('Invalid number of players.')

        self._player_list = []
        for i in range(self._players):
            while True:
                name = input(f'Player {i+1} name: ').strip()
                if name.lower() != 'computer':
                    self._player_list.append(Player(name))
                    break
                else:
                    print("'Computer' is not allowed as a player name.")       

        if self._players == 1:
            self._player_list.append(Player('Computer'))


    def setup_difficulty(self):        
        if self._players == 1:
            difficulties = list(enumerate(self._DIFFICULTIES, 1))
            while True:
                print('Difficulties (' + ', '.join(f'{diff}[{i}]' for i, diff in difficulties) + '): ', end='')
                choice = input().strip()
                if choice.isdigit() and 1 <= int(choice) <= len(difficulties):
                    self._difficulty = self.set_difficulty(list(self._DIFFICULTIES)[int(choice) - 1])           
                    break
                print('Invalid difficulty.')

    def setup_game_type(self):
        game_types = list(enumerate(self._GAME_TYPES, 1))      
        while True:
            print('Game type (' + ', '.join(f'{type}[{i}]' for i, type in game_types) + '): ', end='')
            choice = input().strip()
            if choice.isdigit() and 1 <= int(choice) <= len(game_types):
                self._game_type = self.set_game_type(list(self._GAME_TYPES)[int(choice) - 1])
                break            
            print('Invalid game type.')


    def set_players(self, players):
        if 1 <= players <= self._MAX_PLAYERS:
            return players
        raise ValueError(f'Invalid player count.')


    def set_difficulty(self, difficulty):
        if difficulty in self._DIFFICULTIES:
            return difficulty
        raise ValueError(f'Invalid difficulty.')


    def set_game_type(self, game_type):
        if game_type in self._GAME_TYPES:
            self._words = set()
            for file in self._GAME_TYPES[game_type]['dictionary']:
                with open(file, 'r') as f:
                    self._words.update(f.read().lower().splitlines())
            return game_type
        raise ValueError(f'Invalid game type.')


    def run_game(self):
        game_player_list = self._player_list.copy()
        start_letter = random.choice([letter for letter in string.ascii_uppercase if letter not in 'QXYZ'])
        while True:
            if self._GAME_TYPES[self._game_type]['input_type'] == 1 and self.get_winner().score >= self._WINNING_SCORE:
                break
            elif self._GAME_TYPES[self._game_type]['input_type'] == 2 and len(game_player_list) < 2:
                break
            curr_player = game_player_list[0]
            if curr_player.name.lower() != 'computer':
                score, start_letter = self.run_round_user(curr_player, start_letter)
            else:
                score, start_letter = self.run_round_computer(curr_player, start_letter)
            if self._GAME_TYPES[self._game_type]['input_type'] == 2 and start_letter == '':
                game_player_list =  game_player_list[1:]
                start_letter = random.choice([letter for letter in string.ascii_uppercase if letter not in 'QUXYZ'])
            
            curr_player.change_score(score)

            # print(f'+{score}, Total ({curr_player.name}) = {curr_player.score}')
            if self._GAME_TYPES[self._game_type]['input_type'] == 1:
                scoreboard = ' | '.join(str(player) for player in self._player_list)   

                sys.stdout.write(f'\r+{score}\n{scoreboard}\n')
                sys.stdout.flush()      

            game_player_list = game_player_list[1:] + [game_player_list[0]]
            self._round += 1
        
        print(f'WINNER! {self.get_winner().name}')


    def run_round_user(self, curr_player, start_letter):
        timer = Timer(f'{curr_player.name} ({start_letter})', self._GAME_TYPES[self._game_type]['countdown_time'], self._GAME_TYPES[self._game_type]['input_type'])
        word, time_taken = timer.get_input(lambda w: self.check_word(start_letter, self._words, self._used_words, w))

        if word == '':
            return 0, ''
        elif self._GAME_TYPES[self._game_type]['input_type'] == 2:
            print(word)
        
        self._used_words.add(word.lower())

        score = round(self.get_score(word, time_taken))

        return score, word[-1].upper()
    
    def run_round_computer(self, curr_player, start_letter):
        timer = Timer(f'{curr_player.name} ({start_letter})', self._GAME_TYPES[self._game_type]['countdown_time'], self._GAME_TYPES[self._game_type]['input_type'])
        word = self.choose_word(start_letter)
        word, time_taken = timer.get_input(lambda w: self.check_word(start_letter, self._words, self._used_words, w), True, word)
        self._used_words.add(word.lower())

        score = round(self.get_score(word, time_taken))

        return score, word[-1].upper()
    
    def choose_word(self, start_letter):        
        min_length, max_length, average_length, st_dev = self._DIFFICULTIES[self._difficulty]
        for key, (_, max_len, _, _) in self._DIFFICULTIES.items():
            if max_len is None:
                max_length = len(max(self._words, key=len))

        while True:
            word_len = max(min_length, min(max_length, round(random.gauss(average_length, st_dev))))
            filtered_words = {
                word for word in self._words 
                if len(word) == word_len and self.check_word(start_letter, self._words, self._used_words, word)
            }
            if filtered_words:
                break
        
        return random.choice(list(filtered_words))            


    def get_score(self, word, time_taken):
        return len(word) + self._GAME_TYPES[self._game_type]['countdown_time'] - time_taken    
    
    @staticmethod
    def check_word(start, dict_words, used_words, word=''):
        if len(word) < Shirotori._MIN_WORD_LEN:
            return False
        return word[0].upper() == start.upper() and word.lower() in dict_words and not word.lower() in used_words
    
    def get_winner(self):
        return max(self._player_list, key=lambda player: player.score) 

"""
    A timer class that provides a countdown timer and handles user input.
    
    The `Timer` class is responsible for managing a countdown timer and getting user input within the given time limit. 
    It supports both manual user input and simulated computer input. The timer is displayed to the user as the input is being received.
    
    The class has the following methods:
    
    - `get_input(self, check_func, ai=False, word=None)`: Starts the timer thread and gets user input or computer input. Returns the user input and the elapsed time.
    - `display_timer(self)`: Displays the countdown timer to the user.
    - `get_user_input(self, check_func)`: Handles user input, including backspace and enter key handling.
        - if input_type == 1, then returns blank string as user input once time runs out
        - else runs indefinite loop until user inputs enter key
    - `get_computer_input(self, word)`: Simulates computer input by gradually displaying the characters of the given word.
    - `elapsed_int(self)`: Returns the remaining time on the countdown timer as an integer.
    
    The class also has properties for the prompt and countdown time, which can be set and retrieved.
"""

class Timer:
    def __init__(self, prompt='word', countdown_time=10, input_type=1):
        self._elapsed = 0
        self._input_received = False
        self._user_input = ''
        self._prompt = prompt
        self._countdown_time = countdown_time
        self._input_type = input_type

    def get_input(self, check_func, ai=False, word=None):
        # Start the timer thread
        timer_thread = threading.Thread(target=self.display_timer)
        timer_thread.daemon = True
        timer_thread.start()

        # Get user input
        if not ai:
            self.get_user_input(check_func)
        else:
            computer_thread = threading.Thread(target=self.get_computer_input, args=(word,))
            computer_thread.start()
            computer_thread.join()  # Wait for the computer thread to finish

        # Wait for the timer thread to finish
        timer_thread.join(0.02) 

        # Clear the last timer display
        # sys.stdout.write('\n')
        sys.stdout.write('\r' + ' ' * (len(f'{self.elapsed_int():2} | {self._prompt}: {self._user_input}') + 10) + '\r')
        sys.stdout.flush()
        return self._user_input, self._elapsed

    def display_timer(self):
        start_time = time.time()
        while not self._input_received:
            self._elapsed = time.time() - start_time
            sys.stdout.write(f'\r{self.elapsed_int():2} | {self._prompt}: {self._user_input}')
            sys.stdout.flush()
            time.sleep(0.01)  # Update every 0.01 seconds
    
    def get_user_input(self, check_func):
        while not self._input_received:
            if self._input_type == 2 and self._elapsed >= self._countdown_time:
                self._input_received = True
                self._user_input = ''
                break
            # Get user input
            char = readchar.readkey()
            if char == readchar.key.ENTER:
                if check_func(self._user_input):
                    self._input_received = True
                    break
            elif char == readchar.key.BACKSPACE:
                if self._user_input:
                    self._user_input = self._user_input[:-1]
                    sys.stdout.write('\b \b')  # Erase the last character
                    sys.stdout.flush()
            elif char.isprintable():
                self._user_input += char
                sys.stdout.write(char)
                sys.stdout.flush()



            self._elapsed += 0.1  # Update elapsed time    
    def get_computer_input(self, word):
        base_delay = 0.17
        time.sleep(max(0.2, random.gauss(0.9, 0.2)))
        for char in word:
            delay = max(0.05, random.gauss(base_delay, 0.07))
            time.sleep(delay)
            sys.stdout.write(char)
            self._user_input += char        
            sys.stdout.flush()
        time.sleep(max(0.05, random.gauss(0.3, 0.1)))
        print()  # Add a newline after printing all characters
        self._input_received = True

    def elapsed_int(self):
        if self._elapsed <= self._countdown_time:
            return int(self._countdown_time + 1 - self._elapsed)
        else:
            return int(self._countdown_time - self._elapsed)

    @property
    def prompt(self):
        return self._prompt

    @prompt.setter
    def prompt(self, prompt):
        self._prompt = prompt

    @property
    def countdown_time(self):
        return self._countdown_time

    @countdown_time.setter
    def countdown_time(self, countdown_time):
        if not isinstance(countdown_time, (int, float)) or countdown_time <= 0:
            raise ValueError('Countdown time must be a positive number')
        self._countdown_time = countdown_time
    


def main():
    game = Shirotori()
    print(f'{game.title()}')
    game.setup_players()
    game.setup_difficulty()
    game.setup_game_type()
    game.run_game()


if __name__ == "__main__":
    main()

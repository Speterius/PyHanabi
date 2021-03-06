import random
from packets import GameStateUpdate, CardPlaced, CardBurned, CardPull, InfoUsed, NextTurn


class Deck:

    """ A Class representation of a literal deck of cards from the game Hanabi. Cards have numbers and colors.
    The game server generates a deck at the start. The players can pull cards out and the game state
    can keep track of the number of cards left within the deck."""

    def __init__(self):
        # Store card objects (dictionaries with fields color and number:
        self.cards = []

        # Structure of the deck:
        self.deck_dict = {1: 3,     # Number of ones
                          2: 2,     # Number of twos
                          3: 2,     # Number of threes
                          4: 2,     # Number of fours
                          5: 1}     # Number of fives

        # Available colors:
        self.colors = ['blue', 'red', 'green', 'yellow', 'white']

        # Generate Cards:
        for col in self.colors:                             # For a given color col
            for num, count in self.deck_dict.items():       # For a given number num
                for _ in range(count):                      # Generate a card a number of times given by deck_dict
                    c = {"color": col,
                         "number": num}
                    self.cards.append(c)

        # Printable form of cards list:
        self.deck_state = {}
        self.update_state()

    def update_state(self):
        for col in self.colors:
            self.deck_state[col] = self.get_cards_with_color(col)

    def pull_card(self):
        card = random.choice(self.cards)
        self.cards.remove(card)
        self.update_state()
        return card

    def __str__(self):
        return str(self.deck_state)

    # Returns all cards within the deck with color: col
    def get_cards_with_color(self, col):
        cards_with_color = []
        for card in self.cards:
            if card["color"] == col:
                cards_with_color.append(card)
        return cards_with_color


class TableStashColumn(list):
    def max(self):
        try:
            return max(self)
        except ValueError:
            return 0


class GameState:
    def __init__(self, n_players):
        self.n_players = n_players                                  # Number of players
        n_cards = 4                                                 # Number of cards in one player's hands

        self.deck = Deck()                                          # Cards still in the deck
        self.table_stash = dict.fromkeys(self.deck.colors,
                                         TableStashColumn())        # Cards placed on the table
        self.discard_pile = []                                      # Cards burned/discarded

        assert 2 <= n_players <= 4
        self.player_hands = dict.fromkeys(range(n_players), dict)   # Cards in player's hands

        for player in self.player_hands.keys():

            hand = {0: self.deck.pull_card(),
                    1: self.deck.pull_card(),
                    2: self.deck.pull_card(),
                    3: self.deck.pull_card()}

            self.player_hands[player] = hand

        # OR IN ONE LINE:
        # self.player_hands = {player_id: {i: self.deck.pull_card() for i in range(4)} for player_id in range(n_players)}

        self.current_player = 0                                     # Will only accept game state updates from this id.
        self.action_done = False                                    # To check if next player button is allowed.

        self.info_points: int = 9
        self.life_points: int = 3

        self.started = False
        self.lost = False

    def to_bytes(self, players):

        """ This function converts the necessary game state variables into a DataPacket object from packets."""

        game_state_update = GameStateUpdate(started=self.started,
                                            players=players,
                                            player_hands=self.player_hands,
                                            table_stash=self.table_stash,
                                            discard_pile=self.discard_pile,
                                            info_points=self.info_points,
                                            life_points=self.life_points,
                                            current_player=self.current_player)

        return game_state_update.to_bytes()

    def lose_life_point(self):
        self.life_points -= 1

        if self.life_points == 0:
            self.lost = True

    def lose_info_point(self):
        # Cannot use info points when 0
        self.info_points = max(self.info_points-1, 0)

    def add_info_point(self):
        # Cannot get more info points than 9
        self.info_points = min(self.info_points+1, 9)

    def __str__(self):
        s = "GameState: \n"
        s += f"    Life Points: {self.life_points}\n"
        s += f"    Info Points: {self.info_points}\n"
        s += f"    Current Player: {self.current_player}\n"

    def update(self, event):

        """
        Possible events: InfoUsed, CardBurned, CardPlaced, CardPull, NextTurn

        Returns True on successful update to GameState.       -> denotes 'changed = True' bool
        Returns False, when event request is not possible.    -> denotes 'changed = False' bool, no need to broadcast
        """

        # Only accept events from the current player:
        if self.current_player != event.player:
            print('Not this players turn.')
            return False

        # When a player gives someone info:
        if type(event) is InfoUsed and not self.action_done:

            # If they enoughh points left:
            if self.info_points > 0:

                # Lose a point of info:
                self.lose_info_point()

                # Did a valid action this turn:
                self.action_done = True

                # Successful Update of GameState:
                print('Info point taken')
                return True
            else:
                print('No info left to do that.')
                return False

        # When a player burns a card:
        elif type(event) is CardBurned and not self.action_done:

            # Get an info point back:
            self.add_info_point()

            # Remove the card from the player's hand:
            self.player_hands[event.player][event.card_position] = {"color": 'empty', "number": 0}

            # Add that card to the discard pile:
            self.discard_pile.append(event.card)

            # Did a valid action this turn:
            self.action_done = True

            # Successful Update of GameState:
            print(f'Card burned: {event.card}, info gained.')

            return True

        # When a player places a card on the table:
        elif type(event) is CardPlaced and not self.action_done:

            # Check whether for this color, this number is correct:
            # If yes: -> add card to table stash;
            if event.card["number"] == self.table_stash[event.card["color"]].max() + 1:

                self.table_stash = {key: [*lst, event.card] if event.card["color"] == key else lst
                                    for key, lst in self.table_stash.items()}

                print(f'Correct card placed: {event.card}')

            # If not: -> add card to discard pile and lose a life.
            else:

                self.discard_pile.append(event.card)
                self.lose_life_point()

                print('Wrong card placement, life lost')

            # Take the card out of the player's hand:
            self.player_hands[event.player][event.card_position] = {"color": 'empty', "number": 0}

            # Did a valid action this turn:
            self.action_done = True

            # Successful Update of GameState:
            return True

        # When a player pulls a card:
        elif type(event) is CardPull:

            # Search for the empty slot in a player's hand and pull a card into it:
            for card_position, card in self.player_hands[event.player].items():
                if card["color"] == "empty":
                    self.player_hands[event.player][card_position] = self.deck.pull_card()

                    # Successful Card Pull and update to GameState:
                    print('New card pulled.')
                    return True

            # The search for the card did not return, so the player has all cards already:
            print('Player has all cards. Cannot pull card.')
            return False

        # When a player clicks next turn:
        elif type(event) is NextTurn:

            # Next Turn is only possible if an action has already been done and the player has all cards:

            # Check if the player has all cards:
            has_all_cards = None not in self.player_hands[event.player].values()

            if self.action_done and has_all_cards:

                # Reset action done.
                self.action_done = False

                # rotate through 0->1->...->(n_players - 1)->0
                self.current_player = (self.current_player + 1) % self.n_players
                print('Switched to Next Player')
                return True
            else:
                print('Current Player has not done any of: [Place, Info, Burn]')
                return False

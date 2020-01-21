#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Originally written by Philip Sterne <psterne@minervaproject.com>
#
# Jan 16, 2018 Qifan Yang <qifan@minerva.kgi.edu>
# Added implementation for class Card and Carddeck;
# Added multilingual support to reduce workload

import itertools
import gettext
from datetime import datetime # for random

class Card(object):

    # Ref: Applied PRETTY_SUITS and STR_RANKS structure
    # from https://github.com/worldveil/deuces/

    # Constant for suits and ranks
    PRETTY_SUITS = {
        'h' : u'\u2660', # spades
        'd' : u'\u2764', # hearts
        'c' : u'\u2666', # diamonds
        's' : u'\u2663'  # clubs
    }
    STR_RANKS = ['A'] + [str(__) for __ in range(2, 11)] + ['J', 'Q', 'K']

    def __init__(self, suit, rank):
        if not suit in ['h', 'd', 'c', 's']:
            raise Exception('Unknown Card Suit')
        if not rank in range(1, 13):
            raise Exception('Unknown Card rank')
        self.suit = suit
        self.rank = rank

    def __repr__(self):
        return self.PRETTY_SUITS[self.suit] + ' ' + self.STR_RANKS[self.rank - 1]

    def value_blackjack(self):
        '''Return the value of a card when in the game of Blackjack.

        Input:
            card: A string which identifies the playing card.

        Returns:
            int, indicating the value of the card in blackjack rule.

        Strictly speaking, Aces can be valued at either 1 or 10, this
        implementation assumes that the value is always 1, and then determines
        later how many aces can be valued at 10.  (This occurs in
        blackjack_value.)
        '''
        return (self.rank < 10) * self.rank + (self.rank >= 10) * 10

    def is_ace(self):
        '''Identify whether or not a card is an ace.

        Input:
            card: A string which identifies the playing card.

        Returns:
            true or false, depending on whether the card is an ace or not.
        '''
        return self.rank == 1

class CardDeck(object):

    def __init__(self, status = 'empty'):
        if status == 'empty':
            self.cards = []
        elif status == 'full':
            self.cards = [Card(suit, rank) for suit, rank in itertools.product(Card.PRETTY_SUITS, range(1, 13))]
        else:
            raise Exception('Unknown deck status')

    def __repr__(self):
        # For output
        return str([Card.PRETTY_SUITS[__.suit] + ' ' + Card.STR_RANKS[__.rank - 1] for __ in self.cards])

    def __getitem__(self, key):
        # For indexing
        return self.cards[key]

    def append(self, card):
        if type(card) != Card:
            raise Exception('Invalid Card')
        self.cards.append(card)

    def pop(self, position = None):
        if position == None:
            return cards.pop()
        else:
            return cards.pop(position)

    # Modify the code here for abstraction.
    # ------------------------------------------------------
    def pop_rand(self, rand_method): # require something that implements Random()
        ''' This element returns a random card from a given list of cards.

        Input:
          deck: list of available cards to return.
          x1: variable for use in the generation of random numbers.
          x2: variable for use in the generation of random numbers.
        '''

        rand_generator = self._getRandGenerator(rand_method) # get generator based on arg
        ## tbh, would be way better to set the method on initialization
        rand_num = rand_generator.random_number() # generate number

        return self.cards.pop(rand_num % len(self.cards))
    # ------------------------------------------------------

    def blackjack_value(self):
        '''Calculate the maximal value of a given hand in Blackjack.

        Input:
            cards: A list of strings, with each string identifying a playing card.

        Returns:
            The highest possible value of this hand if it is a legal blackjack
            hand, or -1 if it is an illegal hand.
        '''

        sum_cards = sum([card.value_blackjack() for card in self.cards])
        num_aces = sum([card.is_ace() for card in self.cards])
        aces_to_use = max(int((21 - sum_cards) / 10.0), num_aces)
        final_value = sum_cards + 10 * aces_to_use

        if final_value > 21:
            return -1
        else:
            return final_value

    def _getRandGenerator(self,rand_method):
        '''
        Handler for random method types
        '''
        if rand_method == "randU":
            randu_generator = RandU()
            return(randu_generator)
        elif rand_method == "Mersenne":
            mersenne_generator = Mersenne()
            return(mersenne_generator)
        else:
            raise Exception('Unknown random method')

class Random:
    '''
    interface for random number
    '''
    def random_number(self):
        pass

class RandU(Random):
    '''
    Implementation of randU generator
    '''
    def __init__(self):
        self.x = int((datetime.utcnow() - datetime.min).total_seconds())
        # Constants given by the RANDU algorithm:
        # https://en.wikipedia.org/wiki/RANDU
        self.c = 65539
        self.m = 2147483648

    def random_number(self):
        self.x = abs((self.c * self.x) % self.m) # update x
        return(self.x)

class Mersenne(Random):
    '''
    Implementation of Mersenne generator
    '''
    def __init__(self):
        # bitmasks
        self.bitmask_1 = (2**32) - 1  # To get last 32 bits
        self.bitmask_2 = 2**31  # To get 32nd bit
        self.bitmask_3 = (2**31) - 1  # To get last 31 bits

        # init seeds
        self.seed = int((datetime.utcnow() - datetime.min).total_seconds())
        (self.MT, self.index) = self._initialize_generator()

    def random_number(self):
        (self.MT, self.index, y) = self._extract_number()
        return(y)

    def _initialize_generator(self):
        "Initialize the generator from a seed"
        # Create a length 624 list to store the state of the generator
        self.MT = [0 for i in range(624)]
        self.index = 0
        self.MT[0] = self.seed
        for i in range(1, 624):
            self.MT[i] = ((1812433253 * self.MT[i - 1]) ^ (
                (self.MT[i - 1] >> 30) + i)) & self.bitmask_1
        return (self.MT, self.index)

    def _generate_numbers(self):
        "Generate an array of 624 untempered numbers"
        for i in range(624):
            y = (self.MT[i] & self.bitmask_2) + (self.MT[(i + 1) % 624] & self.bitmask_3)
            self.MT[i] = self.MT[(i + 397) % 624] ^ (y >> 1)
            if y % 2 != 0:
                self.MT[i] ^= 2567483615
        return self.MT

    def _extract_number(self):
        """
        Extract a tempered pseudorandom number based on the index-th value,
        calling generate_numbers() every 624 numbers
        """
        if self.index == 0:
            self.MT = self._generate_numbers()
        y = self.MT[self.index]
        y ^= y >> 11
        y ^= (y << 7) & 2636928640
        y ^= (y << 15) & 4022730752
        y ^= y >> 18

        self.index = (self.index + 1) % 624
        return (self.MT, self.index, y)



def display(player, dealer, args):
    '''Display the current information available to the player.'''
    print(_('The dealer is showing: '), dealer[0])
    print(_('Your hand is: '), player)

def hit_me(args):
    '''Query the user as to whether they want another car or not.

    Returns:
        A boolean value of True or False.  True means that the user does want
        another card.
    '''
    ans = ""
    while ans.lower() not in ('y', 'n'):
        ans = input(_('Would you like another card? (y/n):'))
    return ans.lower() == 'y'

def game(args):

    # Initialize everything

    deck = CardDeck(status = 'full')

    my_hand = CardDeck(status = 'empty')
    dealer_hand = CardDeck(status = 'empty')

    # Deal the initial cards
    for a in range(2):
        card = deck.pop_rand(rand_method = args.rand_method)
        my_hand.append(card)
        card = deck.pop_rand(rand_method = args.rand_method)
        dealer_hand.append(card)

    # Give the user as many cards as they want (without going bust).
    display(my_hand, dealer_hand, args)
    while hit_me(args):
        card = deck.pop_rand(rand_method = args.rand_method)
        my_hand.append(card)
        display(my_hand, dealer_hand, args)
        if my_hand.blackjack_value() < 0:
            print(_('You have gone bust!'))
            break

    # Now deal cards to the dealer:
    print(_("The dealer has: "), repr(dealer_hand))
    while 0 < dealer_hand.blackjack_value() < 17:
        card = deck.pop_rand(rand_method = args.rand_method)
        dealer_hand.append(card)
        print(_('The dealer hits'))
        print(_('The dealer has: '), repr(dealer_hand))

    if dealer_hand.blackjack_value() < 0:
        print(_("The dealer has gone bust!"))
    else:
        print(_('The dealer sticks with: '), repr(dealer_hand))

    # Determine who has won the game:
    my_total = my_hand.blackjack_value()
    dealer_total = dealer_hand.blackjack_value()
    if dealer_total == my_total:
        print(_("It's a draw!"))
    if dealer_total > my_total:
        print(_("The dealer won!"))
    if dealer_total < my_total:
        print(_("You won!"))


if __name__ == '__main__':

    import argparse

    parser = argparse.ArgumentParser(description="BlackJack Game")
    # Note that the rand_method argument is not enabled in code!
    parser.add_argument('--rand_method', default='randU',
                        help='The random number generator method. Choose between \'Mersenne\' and \'randU\'.')
    args = parser.parse_args()

    gettext.bindtextdomain('blackjack', 'locale/')
    gettext.textdomain('blackjack')
    _ = gettext.gettext

    print()
    print('BlackJack')
    print('-' * 30)
    print(vars(args))
    print('-' * 30)
    print()

    game(args)

    print()

'''
Question answers:

no coding, file directory + function call knowledge
abstraction cause no need to know how it works/ mess with any existing code.

objects are better abstraction. card and deck can be modified seperately. (modifying rank actually still touches both, but suits can be modified with just card). But card decks are pretty standard so its probably fine. card valuation rules can be modified in card and card dealing rules can be modified in deck.

everytime we call pop random.
we just care about getting the random number


'''

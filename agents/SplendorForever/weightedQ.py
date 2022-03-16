from template import Agent
from Splendor.splendor_utils import COLOURS
import numpy as np
from copy import deepcopy

ORIGINAL_COLOURS = COLOURS.values()
GEMCOLOUR = []
for color in ORIGINAL_COLOURS:
    if color != 'yellow':
        GEMCOLOUR.append(color)
GEMCOLOUR.append('yellow')
YELLOW_GEM_INDEX = GEMCOLOUR.index('yellow')

COLLECTING_WEIGHT = [112.64661838950887, -14.386494731306968, 85.30001061694689,
                     27.561822164334924, 15.071411126548497, 98.47216676685026, -191.61509731001263]
RESERVING_WEIGHT = [795.808029566221, -16.74076418158996, 42.67360272555004,
                    200.2676167568528, 11.877326175576208, -300.04900618801804]
BUYING_WEIGHT = [29.74592413781117, 1874.6563609868183, 481.36939659662386,
                 -92.63851465136467, -24.081713292112326, 8.792238589124931,
                 69.08843226142527, 12.78014858947157, 34.70924434152265,
                 129.5885142851314, -503.37694061210385, 17.83878233956241]

# get information about a particular gem card
def card_info(card):
    cards_info = [card.points]
    for color in GEMCOLOUR[:-1]:
        count = 0
        if color in card.cost:
            count += card.cost[color]
        cards_info.append(count)
    return np.array(cards_info)

# get information about agent's reserved cards
def get_reserveds(agent):
    reserved = []
    for card in agent.cards['yellow']:
        reserved.append(card_info(card))
    return np.array(reserved)


# get all cards currently on board
def get_cards_on_board(board):
    all_cards = []
    for card in board.dealt_list():
        all_cards.append(card_info(card))
    return np.array(all_cards)


# get cost information about a particular noble card
def get_noble_info(noble):
    noble_info = []
    for color in GEMCOLOUR[:-1]:
        count = 0
        if color in noble[1]:
            count = noble[1][color]
        noble_info.append(count)
    return noble_info


# get the cost information of all nobles on board
def get_noble_on_boards(board):
    nobles_info = []
    for noble in board.nobles:
        nobles_info.append(get_noble_info(noble))
    return np.array(nobles_info)


# get agent's score, card-buying ability and owning_cards (noble-inviting ability)
# buying ability per color = owning gems per color + owning cards per color
def get_agent_ability(agent):
    buying_ability = []
    owning_cards = []
    for color in GEMCOLOUR[:-1]:
        temp_color_count = agent.gems[color]
        temp_card_count = 0
        if agent.cards[color]:
            temp_color_count += len(agent.cards[color])
            temp_card_count = len(agent.cards[color])
        buying_ability.append(temp_color_count)
        owning_cards.append(temp_card_count)
    return agent.score, np.array(buying_ability), np.array(owning_cards)


class myAgent(Agent):
    def __init__(self, _id):
        super().__init__(_id)
        self.id = _id

    # calculate actual relative gem price based on player holding cards
    def card_price(self, cost, player_gem_cards):
        distance = np.array([0, 0, 0, 0, 0])
        for i in range(5):
            if cost[i] - player_gem_cards[i] > 0:
                distance[i] = cost[i] - player_gem_cards[i]
        return sum(distance)

    # check if a low-score(<= 1) card worths its price
    def is_cheap_low_score(self, cost, player_gem_cards, maximum_all, maximum_per):
        temp = 1
        if np.count_nonzero(cost) == 5:  # only requires gems of one same colour
            if self.card_price(cost, player_gem_cards) > (maximum_all) - 1:
                temp = 0
        else:  # need more than 1 colour
            for i in cost:
                if i > maximum_per:
                    temp = 0
        return temp

    # check if a certain card is great buy for current player state
    def is_great_buy(self, cost, my_gem_cards, enemy_gem_cards, my_score, enemy_score, score):
        temp = 0
        # game earlier stage
        if my_score < 10 and enemy_score < 10:
            # game just start
            if sum(my_gem_cards) < 4 and sum(enemy_gem_cards) < 4:
                if score <= 1 and self.card_price(cost, my_gem_cards) <= 3:
                    # gem required at most 2 per colour, totol less than 5
                    temp += self.is_cheap_low_score(cost, my_gem_cards, 4, 2)
                elif score >= 2 and self.card_price(cost, my_gem_cards) / score <= 2:
                    temp += 1
            # game transitional period
            else:
                if score <= 1 and self.card_price(cost, my_gem_cards) <= 3:
                    # gem required at most 2 per colour, totol less than 4
                    temp += self.is_cheap_low_score(cost, my_gem_cards, 3, 2)
                elif score >= 2 and self.card_price(cost, my_gem_cards) / score < 2:
                    temp += 1
        # game final stage
        else:
            if score >= 2 and self.card_price(cost, my_gem_cards) / score < 2:
                temp += 1
                if self.card_price(cost, my_gem_cards) / score < 1:
                    temp += 1
        return temp

    # extract great buy cards from giving card list
    def get_great_buys(self, my_gem_cards, enemy_gem_cards, my_score, enemy_score, cards_list):
        great_temp = []
        else_temp = []
        for each in cards_list:
            cost = each[1:].astype(np.float)
            score = each[0].astype(np.float)
            if self.is_great_buy(cost, my_gem_cards, enemy_gem_cards, my_score, enemy_score, score) > 0:
                great_temp.append(each)
            else:
                else_temp.append(each)
        return great_temp, else_temp

    # check whether this player buying ability can afford this card
    def if_afford_card(self, cost, player_buying_ability):
        temp_gap = cost - player_buying_ability
        for i in range(5):
            if temp_gap[i] > 0:
                return False
        return True

    # 7 features for collecting actions
    # feature 1: be beneficial for subsequent buying of great-buy cards on board
    # feature 2: be beneficial for subsequent buying of other (not great buy) cards on board
    # feature 3: be beneficial for subsequent buying of my reserved cards
    # feature 4: be beneficial for enemy subsequent buying of their reserved cards
    # feature 5: be beneficial for enemy subsequent buying of all cards on the board
    # feature 6: if in game earlier stage, whether agent is holding less than 7 gems
    # feature 7：Whether to collect 3 gems (full collect), how much less, if there are any returns
    def collecting_features(self, game_state, action):
        my_agent = game_state.agents[self.id]
        my_score, my_buying_ability, my_gem_cards = get_agent_ability(my_agent)
        my_reserve_cards = get_reserveds(my_agent)

        enemy_agent = game_state.agents[1 - self.id]
        enemy_score, enemy_buying_ability, enemy_gem_cards = get_agent_ability(enemy_agent)
        enemy_reserve_cards = get_reserveds(enemy_agent)

        cards_on_board = get_cards_on_board(game_state.board)

        # what gems are needed for buying each card from cards list
        def get_cards_needs(player_buying_ability, player_gem_cards, cards_list):
            temp_needs = []
            for card in cards_list:
                temp_need = card[1:].astype(np.float) - player_buying_ability
                for i in range(len(temp_need)):
                    temp_need[i] = max(0, temp_need[i])
                temp_needs.append(temp_need)
            return temp_needs

        # check how much beneficial this collecting action would be for buying card / inviting nobles from different card pools
        # which means how many cards/nobles need this color
        def how_much_beneficial(all_needs):
            beneficial_count = 0
            for needs in all_needs:
                for colour in action['collected_gems'].keys():
                    colour_count = action['collected_gems'][colour]
                    if needs[GEMCOLOUR.index(colour)] > 0:
                        beneficial_count += min(needs[GEMCOLOUR.index(colour)], colour_count)
            return beneficial_count

        features = []
        # feature 1: be beneficial for subsequent buying of great-buy cards on board,
        # feature 2: be beneficial for subsequent buying of other (not great buy) cards on board
        # feature 3: be beneficial for subsequent buying of my reserved cards
        # feature 4: be beneficial for enemy subsequent buying of their reserved  cards
        # feature 5: be beneficial for enemy subsequent buying of all cards on the board
        all_gem_needs = []
        for i in range(2):
            all_gem_needs.append(get_cards_needs(my_buying_ability, my_gem_cards,
                                                 self.get_great_buys(my_gem_cards, enemy_gem_cards, my_score,
                                                                     enemy_score, cards_on_board)[i]))

        all_gem_needs.append(get_cards_needs(my_buying_ability, my_gem_cards, my_reserve_cards))
        all_gem_needs.append(get_cards_needs(enemy_buying_ability, enemy_gem_cards, enemy_reserve_cards))
        all_gem_needs.append(get_cards_needs(enemy_buying_ability, enemy_gem_cards, cards_on_board))

        for needs in all_gem_needs:
            features.append(how_much_beneficial(needs))

        # feature 6: if in game earlier stage, whether agent is holding less than 7 gems
        if my_score < 10 and enemy_score < 10 and sum(my_agent.gems.values()) <= 7:
            features.append(1)
        else:
            features.append(0)

        # feature 7：Whether to collect 3 gems (full collect), how much less, if there are any returns
        full_collect_distance = 0
        if (len(action['collected_gems']) < 3):
            full_collect_distance += (3 - len(action['collected_gems']))
        if action['returned_gems']:
            for colour in action['returned_gems']:
                full_collect_distance += action['returned_gems'][colour]
        features.append(full_collect_distance)

        return features

    # 12 features for buying actions
    # feature 1：if it is a great buy card for current game stage
    # feature 2：score / relative cost
    # feature 3: can inviting nobles after this buying
    # feature 4: whether need to consume yellow gem
    # feature 5: colour is beneficial for subsequent buying of geat-buy cards on board
    # feature 6: colour is beneficial for subsequent buying of geat-buy cards on board
    # feature 7: colour is beneficial for subsequent buying of reserved cards
    # feature 8: colour is beneficial for enemy subsequent buying of cards on board
    # feature 9: colour is beneficial for enemy subsequent buying of reserved cards
    # feature 10: colour is beneficial for inviting nobles
    # feature 11: already have more than 4 cards of same colour
    # feature 12: have less than 2 cards of same colour
    def buying_features(self, game_state, action):
        my_agent = game_state.agents[self.id]
        my_score, my_buying_ability, my_gem_cards = get_agent_ability(my_agent)
        my_reserve_cards = get_reserveds(my_agent)

        enemy_agent = game_state.agents[1 - self.id]
        enemy_score, enemy_buying_ability, enemy_gem_cards = get_agent_ability(enemy_agent)
        enemy_reserve_cards = get_reserveds(enemy_agent)

        cards_on_board = get_cards_on_board(game_state.board)
        nobles_on_board = get_noble_on_boards(game_state.board)
        colour_index = GEMCOLOUR.index(action['card'].colour)

        # return any changes(score and gem) brought by a certain action
        def result_of_buy(action):
            score_change = card_info(action['card'])[0]
            card_cost = card_info(action['card'])[1:]
            return score_change, np.array(card_cost)

        score, cost = result_of_buy(action)

        def how_much_beneficial(cards, player_gem_cards):
            count = 0
            for card in cards:
                if float(card[colour_index + 1]) - player_gem_cards[colour_index] > 0:
                    count += 1
            return count

        def how_much_beneficial_noble(cards, player_gem_cards):
            count = 0
            for card in cards:
                if float(card[colour_index]) - player_gem_cards[colour_index] > 0:
                    count += 1
            return count

        features = []

        # feature 1：if it is a great buy card for current game stage
        features.append(self.is_great_buy(cost, my_gem_cards, enemy_gem_cards, my_score, enemy_score, score))

        # feature 2：score / relative cost
        if self.card_price(cost, my_gem_cards) > 0:
            features.append(score / self.card_price(cost, my_gem_cards))
        else:
            features.append(score * 1.5)

        # feature 3: can inviting nobles after this buying
        new_noble = 3 if action['noble'] != None else 0
        features.append(new_noble)

        # feature 4: whether need to consume yellow gem
        if 'yellow' in action['returned_gems']:
            features.append(action['returned_gems']['yellow'])
        else:
            features.append(0)

        # feature 5: colour is beneficial for subsequent buying of geat-buy cards on board
        features.append(how_much_beneficial(
            self.get_great_buys(my_gem_cards, enemy_gem_cards, my_score, enemy_score, cards_on_board)[0], my_gem_cards))

        # feature 6: colour is beneficial for subsequent buying of geat-buy cards on board
        features.append(how_much_beneficial(
            self.get_great_buys(my_gem_cards, enemy_gem_cards, my_score, enemy_score, cards_on_board)[1], my_gem_cards))

        # feature 7: colour is beneficial for subsequent buying of reserved cards
        features.append(how_much_beneficial(my_reserve_cards, my_gem_cards))

        # feature 8: colour is beneficial for enemy subsequent buying of cards on board
        if self.if_afford_card(cost, enemy_buying_ability):
            features.append(how_much_beneficial(cards_on_board, enemy_gem_cards))
        else:
            features.append(0)

        # feature 9: colour is beneficial for enemy subsequent buying of reserved cards
        if self.if_afford_card(cost, enemy_buying_ability):
            features.append(how_much_beneficial(enemy_reserve_cards, enemy_gem_cards))
        else:
            features.append(0)

        # feature 10: colour is beneficial for inviting nobles
        features.append(how_much_beneficial_noble(nobles_on_board, my_gem_cards))

        # feature 11: already have more than 4 cards of same colour
        temp = 1 if my_gem_cards[colour_index] >= 5 else 0
        features.append(temp)

        # feature 12: have less than 2 cards of same colour
        temp = 1 if my_gem_cards[colour_index] < 2 else 0
        features.append(temp)

        return features

    # 6 features for reserving actions
    # feature 1: is a great buy card, but currently cannot afford, worth a reservation
    # feature 2: how much beneficial for my subsequent buying
    # feature 3: how much beneficial for inviting nobles
    # feature 4: significant for enemy (they can afford), may be high-score, or they can invite nobles immediately after buying
    # feature 5: how much beneficial for enemy subsequent buying (enemy can afford)
    # feature 6：whether fail to collect yellow gem
    def reserving_features(self, game_state, action):
        board = game_state.board
        my_agent = game_state.agents[self.id]
        my_score, my_buying_ability, my_gem_cards = get_agent_ability(my_agent)
        my_reserve_cards = get_reserveds(my_agent)

        enemy_agent = game_state.agents[1 - self.id]
        enemy_score, enemy_buying_ability, enemy_gem_cards = get_agent_ability(enemy_agent)
        enemy_reserve_cards = get_reserveds(enemy_agent)

        cards_on_board = get_cards_on_board(board)
        nobles_on_board = get_noble_on_boards(board)
        colour_index = GEMCOLOUR.index(action['card'].colour)

        features = []
        r_card = card_info(action['card'])

        score = r_card[0]
        cost = r_card[1:]
        colour = action['card'].colour

        # check how many cards need the colour of this card
        def how_much_beneficial_card(player_gem_cards, player_buying_ability, cards):
            count = 0
            for card in cards:
                if float(card[colour_index + 1]) - player_gem_cards[colour_index] > 0:
                    count += 1
            return count

        # check how many nobles need this card colour
        def how_much_beneficial_noble(player_gem_cards, player_buying_ability, cards):
            count = 0
            for card in cards:
                if float(card[colour_index]) - player_gem_cards[colour_index] > 0:
                    count += 1
            return count

        # feature 1: check whether this card worths to be resverved
        def is_great_reserve(player_gem_cards):
            temp = 0
            # game earlier stage
            if my_score < 10 and enemy_score < 10:
                # game just start
                if sum(my_gem_cards) < 4 and sum(enemy_gem_cards) < 4:
                    if score >= 4 and self.card_price(cost, player_gem_cards) / score <= 2:
                        temp = 1
                # game transitional perod
                else:
                    if score >= 4 and self.card_price(cost, player_gem_cards) / score < 2:
                        temp = 1
            # game final stage
            else:
                if score >= 4:
                    temp = 1
            return temp

        temp = is_great_reserve(my_gem_cards)
        features.append(temp)

        # feature 2: beneficial for my subsequent buying
        # for cards on board, reserved cards
        temp_need = how_much_beneficial_card(my_gem_cards, my_buying_ability, cards_on_board) \
                    + 1.5 * how_much_beneficial_card(my_gem_cards, my_buying_ability, my_reserve_cards)
        features.append(temp_need)

        # feature 3: beneficial for inviting nobles on board
        features.append(how_much_beneficial_noble(my_gem_cards, my_buying_ability, nobles_on_board))

        # method for checking whether new noble will be invited after enemy buying this card
        def if_inviting_noble(card, player_gem_cards):
            temp_gap = card - player_gem_cards
            for i in range(5):
                if temp_gap[i] > 0:
                    return False
            return True

        # feature 4: significant for enemy
        temp = 0
        if self.if_afford_card(cost, enemy_buying_ability):  # enemy can afford this card
            temp += 0.5
            if score >= 4:  # it is high-score card
                temp += 1
            for noble in nobles_on_board:  # can invite nobles immediately after buying
                card_change = np.array([0, 0, 0, 0, 0])
                card_change[colour_index] = 1
                if if_inviting_noble(noble, enemy_gem_cards) != False and if_inviting_noble(noble,
                                                                                            enemy_gem_cards + card_change) == True:
                    temp += 1
        features.append(temp)

        # feature 5: beneficial for enemy subsequent buying
        temp = 0
        # enemy can afford this card
        if self.if_afford_card(cost, enemy_buying_ability):
            # beneficial for buy cards on board, buy enemy reserved cards, inviting nobles
            temp = how_much_beneficial_card(enemy_gem_cards, enemy_buying_ability, cards_on_board) \
                   + 1.5 * how_much_beneficial_card(enemy_gem_cards, enemy_buying_ability, enemy_reserve_cards) \
                   + 1.5 * how_much_beneficial_noble(enemy_gem_cards, enemy_buying_ability, nobles_on_board)
        features.append(temp)

        # feature 6：whether fail to collect yellow gem
        failed_collect = 1 if not action["collected_gems"] or action['returned_gems'] else 0
        features.append(failed_collect)

        return features

    # selectAction method for unchange action feature weights, no need to update weights
    def SelectAction(self, actions, game_state):
        best_action = None
        best_value = -99999

        # calculate q value for every available action
        # find the one with the best q value -> best action
        for action in actions:
            if "collect" in action["type"]:
                temp_features = self.collecting_features(game_state, action)
                temp_weights = COLLECTING_WEIGHT
            elif action["type"] == "reserve":
                temp_features = self.reserving_features(game_state, action)
                temp_weights = RESERVING_WEIGHT
            elif "buy" in action["type"]:
                temp_features = self.buying_features(game_state, action)
                temp_weights = BUYING_WEIGHT

            qValue = sum(np.multiply(temp_features, temp_weights))
            if qValue > best_value:
                best_value = qValue
                best_action = action

        return best_action

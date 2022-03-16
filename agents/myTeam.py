import sys
sys.path.append('teams/SplendorForever')
from template import Agent
import time
from copy import copy
from Splendor.splendor_model import SplendorGameRule as GameRule
import random, itertools
from math import sqrt
from numpy import log as ln

THINKTIME = 0.998
agent_number = 2
game_rule = GameRule(agent_number)

# FUNCTIONS ----------------------------------------------------------------------------------------------------------

def get_relative_distance(agent_buying_ability, card):

    distance = 0
    for color, costs in card.cost.items():
        difference = costs - agent_buying_ability.get(color)
        if difference > 0:
            distance += difference

    distance - agent_buying_ability.get('yellow')

    return distance

class Action_Type():

    def __init__(self, agent, opponent, board, potential_nobles, good_card, agent_buying_ability, relative_distance):
        self.agent = agent
        self.opponent = opponent
        self.board = board
        self.potential_nobles = potential_nobles
        self.good_card = good_card
        self.agent_buying_ability = agent_buying_ability
        self.relative_distance = relative_distance
        self.opponent_card = []
        self.actions_rewards = {}
        self.collection_reward = 0
        self.buy_reward = 0

    def buy_card(self):
        for card in self.board.dealt_list() + self.agent.cards['yellow']:
            if len(self.opponent.cards[card.colour]) < 7:
                returned_gems = game_rule.resources_sufficient(self.opponent, card.cost)
                if type(returned_gems)==dict:
                    noble_check = False
                    opponent_post_action = copy(self.opponent)
                    post_action_cards = copy(opponent_post_action.cards)
                    color_cards = copy(post_action_cards[card.colour])
                    color_cards.append(card)
                    post_action_cards[card.colour] = color_cards
                    opponent_post_action.cards = post_action_cards
                    for noble in self.board.nobles:
                        if game_rule.noble_visit(opponent_post_action, noble):
                            noble_check = True
                            break
                    if noble_check or card.points > 2:
                        self.opponent_card.append(card)

            if not card or len(self.agent.cards[card.colour]) == 7:
                continue
            returned_gems = game_rule.resources_sufficient(self.agent, card.cost) #Check if this card is affordable.
            if type(returned_gems)==dict: #If a dict was returned, this means the agent possesses sufficient resources.
                #Check to see if the acquisition of a new card has meant new nobles becoming candidates to visit.
                new_nobles = []
                agent_post_action = copy(self.agent)
                post_action_cards = copy(agent_post_action.cards)
                color_cards = copy(post_action_cards[card.colour])
                color_cards.append(card)
                post_action_cards[card.colour] = color_cards
                agent_post_action.cards = post_action_cards
                for noble in self.board.nobles:
                    #Use this copied agent to check whether this noble can visit.
                    if game_rule.noble_visit(agent_post_action, noble):
                        new_nobles.append(noble) #If so, add noble to the new list.
                if not new_nobles:
                    new_nobles = [None]
                for noble in new_nobles:
                    action = {'type': 'buy_reserve' if card in self.agent.cards['yellow'] else 'buy_available',
                                'card': card,
                                'returned_gems': returned_gems,
                                'noble': noble}

                    reward = self.calculate_reward(action)

                    if self.actions_rewards.get(reward):
                        self.actions_rewards[reward].append(action)
                    else:
                        self.actions_rewards[reward] = [action]

    def reserve_card(self):
        if len(self.agent.cards['yellow']) < 3:
            collected_gems = {'yellow':1} if self.board.gems['yellow']>0 else {}
            return_combos = game_rule.generate_return_combos(self.agent.gems, collected_gems)
            for returned_gems in return_combos:
                for card in self.board.dealt_list():
                    if card:
                        for noble in self.potential_nobles:
                            action = {'type': 'reserve',
                                            'card': card,
                                            'collected_gems': collected_gems,
                                            'returned_gems': returned_gems,
                                            'noble': noble}

                            reward = self.calculate_reward(action)

                            if self.actions_rewards.get(reward):
                                self.actions_rewards[reward].append(action)
                            else:
                                self.actions_rewards[reward] = [action]

    def collect_different_gems(self):

        #Generate actions (collect up to 3 different gems). Work out all legal combinations. Theoretical max is 10.
        available_colours = [colour for colour,number in self.board.gems.items() if colour!='yellow' and number>0]
        for combo_length in range(1, min(len(available_colours), 3) + 1):
            for combo in itertools.combinations(available_colours, combo_length):
                collected_gems = {colour:1 for colour in combo}

                #Find combos of gems to return, if any. Since the max to be returned can be 3, theoretical max
                #combinations will be 51, and max actions generated by the end of this stage will be 510.
                #Handling this branching factor properly will be crucial for agent performance.
                #If return_combos comes back False, then taking these gems is invalid and won't be added.
                return_combos = game_rule.generate_return_combos(self.agent.gems, collected_gems)
                for returned_gems in return_combos:
                    for noble in self.potential_nobles:
                        action = {'type': 'collect_diff',
                                    'collected_gems': collected_gems,
                                    'returned_gems': returned_gems,
                                    'noble': noble}

                        reward = self.calculate_reward(action)

                        if self.actions_rewards.get(reward):
                            self.actions_rewards[reward].append(action)
                        else:
                            self.actions_rewards[reward] = [action]

    def collect_identical_gems(self):

        #Generate actions (collect 2 identical gems). Theoretical max is 5.
        available_colours = [colour for colour,number in self.board.gems.items() if colour!='yellow' and number>=4]
        for colour in available_colours:
            collected_gems = {colour:2}

            #Like before, find combos to return, if any. Since the max to be returned is now 2, theoretical max
            #combinations will be 21, and max actions generated here will be 105.
            return_combos = game_rule.generate_return_combos(self.agent.gems, collected_gems)
            for returned_gems in return_combos:
                for noble in self.potential_nobles:
                    action = {'type': 'collect_same',
                                    'collected_gems': collected_gems,
                                    'returned_gems': returned_gems,
                                    'noble': noble}

                    reward = self.calculate_reward(action)

                    if self.actions_rewards.get(reward):
                        self.actions_rewards[reward].append(action)
                    else:
                        self.actions_rewards[reward] = [action]

    def back_up(self):

        if not self.actions_rewards:
            for noble in self.potential_nobles:
                action = {'type': 'pass', 'noble':noble}

                reward = self.calculate_reward(action)

                if self.actions_rewards.get(reward):
                    self.actions_rewards[reward].append(action)
                else:
                    self.actions_rewards[reward] = [action]

    def calculate_reward(self, action):

        reward = 0

        if action['type'] == 'buy_available' or  action['type'] == 'buy_reserve':
            # edge case, if my reserved area is empty, then the value of a card should be same as 
            # the higher score between highest collection reward and reserved reward
            # if my reserved area is not empty, then the value of a card should be same as highest collection reward
            reward += max(self.collection_reward, 32) if len(self.agent.cards['yellow']) < 3 else self.collection_reward
            if sum(action['returned_gems'].values()) < 5 or action['card'].points > 1:
                reward += 300* (action['card'].points)
            if action['card'] in self.good_card:
                reward += 90
            self.buy_reward = max(self.buy_reward, reward)

        elif action['type'] == 'reserve':
            reward += 30*sum(action['collected_gems'].values())
            reward += 2 if action['card'].points > 1 else 0
            reward -= 30*sum(action['returned_gems'].values())
            # if getting a yellow gem can help agent buy a great card immediately next turn, then we change reserve reward to highest collection_reward 
            if action['card'].points > 2:
                post_agent_buying_ability = self.get_post_agent_buying_ability(action['collected_gems'], action['returned_gems'])
                reward = max(reward, self.collection_reward) if get_relative_distance(post_agent_buying_ability, action['card']) == 0 else reward
            reward = max(self.collection_reward, self.buy_reward) if action['card'] in self.opponent_card else reward
    
        elif action['type'] == 'collect_diff' or action['type'] == 'collect_same':
            reward += 20 * sum(action['collected_gems'].values())
            reward -= 30* sum(action['returned_gems'].values())
            reward -= 10*action['returned_gems']['yellow'] if action['returned_gems'].get('yellow') else 0
            post_agent_buying_ability = self.get_post_agent_buying_ability(action['collected_gems'], action['returned_gems'])
            reward += self.get_extra_collection_reward(post_agent_buying_ability)
            self.collection_reward = max(self.collection_reward, reward)
    
        if action['noble'] != None:
            reward += 900

        return reward

    def get_extra_collection_reward(self, post_agent_buying_ability):

        extra_score = 0

        for card in self.good_card:
            extra_score +=  (card.points + 1) * (self.relative_distance[card.code] - get_relative_distance(post_agent_buying_ability, card))

        return extra_score * 0.1

    def get_post_agent_buying_ability(self, collections, returns):

        post_agent_buying_ability = copy(self.agent_buying_ability)

        for color in collections.keys():
            post_agent_buying_ability[color] = post_agent_buying_ability[color] + collections[color]

        for color in returns.keys():
            post_agent_buying_ability[color] = post_agent_buying_ability[color] - returns[color]

        return post_agent_buying_ability

class State():

    def __init__(self, board, agents):
        self.board = board
        self.agents = agents

class TreeNode():

    def __init__(self, agent_id, game_state, parent):
        self.game_state = game_state 
        self.parent = parent 
        self.agent_id = agent_id   
        self.reward = 0 
        self.visits = 0 
        self.children = {} 
        self.isFullyExpanded = False  
        self.terminate = (self.game_state.agents[agent_id].score >= 15)
        self.enemy_terminate = (self.game_state.agents[1-agent_id].score >= 15)

class MCTS():

    def __init__(self, exploration_constant, game_state, agent_id):
        self.exploration_constant = exploration_constant
        self.game_state = game_state
        self.agent_id = agent_id

    def get_action(self):

        node = TreeNode(self.agent_id, self.game_state, None)

        start_time = time.time()
        
        #counter = 0

        while time.time() - start_time < THINKTIME:

            new_node = self.selection(node)
            reward = self.simulation(new_node)
            self.backpropagation(new_node, reward)
            #counter += 1

        #print(counter)

        best_node = self.choose_best_node(node, 0)

        return node.children.get(best_node)

    def selection(self, node):

        while not node.terminate:
            # expand the node if the node is not fully expanded
            if not node.isFullyExpanded:
                return self.expansion(node)
            # if the current node is fully expanded, apply UCB1 to find next node to check
            else:
                node = self.choose_best_node(node, self.exploration_constant)

        return node

    def expansion(self, node):

        # get all appropriate actions of current node
        actions = self.get_appropriate_actions(node.game_state, node.agent_id)
        # get pruned actions
        pruned_actions = [action for action in actions if action not in node.children.values()]
        # choose a pruned action
        action = random.choice(pruned_actions)
        # get next game state
        new_state = self.generateSuccessor(node.game_state, action, node.agent_id)
        # get next agent id
        new_agent_id = 1 - node.agent_id
        # create a new node for the next state
        new_node = TreeNode(new_agent_id, new_state, node)
        # add new node and the action to new node as current node's child
        node.children[new_node] = action

        # check whether the current node is fully expanded
        if len(node.children) == len(actions):
            node.isFullyExpanded = True

        return new_node

    def simulation(self, node):

        depth = 0

        reward = 0

        while not node.terminate and not node.enemy_terminate:

            actions = self.get_appropriate_actions(node.game_state, node.agent_id)
            # choose an action
            action = random.choice(actions)
            # get new reward
            reward += self.get_reward(action) if node.agent_id == self.agent_id else -self.get_reward(action)
            # get next game state
            new_state = self.generateSuccessor(node.game_state, action, node.agent_id)
            # get next agent id
            new_agent_id = 1 - node.agent_id
            # create a new node for the next state
            node = TreeNode(new_agent_id, new_state, node)

            depth += 1

            if depth == 10:
                break

        return reward

    def backpropagation(self, node, reward):

        while node != None:
            node.visits += 1
            node.reward += reward
            node = node.parent

    def choose_best_node(self, node, exploration_constant):

        best_nodes = []
        best_value = float("-inf")

        # Apply UCB1
        for child in node.children.keys():
            node_value = child.reward + (2*exploration_constant * sqrt(2*ln(node.visits) / child.visits))

            if node_value > best_value:
                best_value = node_value
                best_nodes = [child]

            elif node_value == best_value:
                best_nodes.append(child)

        return random.choice(best_nodes)

    def get_reward(self, action):

        reward = 0

        if action['type'] == 'buy_available' or  action['type'] == 'buy_reserve':
            reward += (300 * (action['card'].points) + 100)
       
        elif action['type'] == 'reserve':
            reward += 30*sum(action['collected_gems'].values())
            reward -= 30*sum(action['returned_gems'].values())

        elif action['type'] == 'collect_diff' or action['type'] == 'collect_same':
            reward += 20 * sum(action['collected_gems'].values())
            reward -= 30* sum(action['returned_gems'].values())
            reward -= 10*action['returned_gems']['yellow'] if action['returned_gems'].get('yellow') else 0

        if action['noble'] != None:
            reward += 900
          
        return reward

    def get_appropriate_actions(self, game_state, agent_id):

        board = game_state.board
        agent = game_state.agents[agent_id]
        opponent = game_state.agents[1-agent_id]

        agent_buying_ability = {}
        for color, card in agent.cards.items():
            if color != 'yellow':
                agent_buying_ability[color] = agent.gems[color] + len(card)
            else:
                agent_buying_ability[color] = agent.gems[color]

        potential_nobles = []
        noble_color =[]
        for noble in board.nobles:
            noble_color += (noble[1].keys())
            if game_rule.noble_visit(agent, noble):
                potential_nobles.append(noble)
        if len(potential_nobles) == 0:
            potential_nobles = [None]

        good_card = copy(agent.cards['yellow'])
        for card in board.dealt_list():
            if (card.colour in noble_color and len(agent.cards[card.colour]) < 4) or card.points > 1: 
                good_card.append(card)

        relative_distance = {}
        for card in good_card:
            relative_distance[card.code] = get_relative_distance(agent_buying_ability, card)

        action_types = Action_Type(agent, opponent, board, potential_nobles, good_card, agent_buying_ability, relative_distance)
        action_types.collect_different_gems()
        action_types.collect_identical_gems()
        action_types.buy_card()
        action_types.reserve_card()
        action_types.back_up()

        actions_rewards = action_types.actions_rewards
        actions = action_types.actions_rewards[max(actions_rewards.keys())]

        return actions

    def generateSuccessor(self, state, action, agent_id):

        board = copy(state.board)
        agents = copy(state.agents)
        agent = copy(agents[agent_id])
        agent.last_action = action
        score = 0

        if 'card' in action:
            card = action['card']

        if 'collect' in action['type'] or action['type']=='reserve':
            #Decrement board gem stacks by collected_gems. Increment player gem stacks by collected_gems.
            for colour,count in action['collected_gems'].items():

                board_gems = copy(board.gems)
                agent_gems = copy(agent.gems)

                board_gems[colour] -= count
                agent_gems[colour] += count

                board.gems = board_gems
                agent.gems = agent_gems

            #Decrement player gem stacks by returned_gems. Increment board gem stacks by returned_gems.
            for colour,count in action['returned_gems'].items():

                board_gems = copy(board.gems)
                agent_gems = copy(agent.gems)

                board_gems[colour] += count
                agent_gems[colour] -= count

                board.gems = board_gems
                agent.gems = agent_gems

            if action['type'] == 'reserve':
                #Remove card from dealt cards by locating via unique code (cards aren't otherwise hashable).
                #Since we want to retain the positioning of dealt cards, set removed card slot to new dealt card.
                #Since the board may have None cards (empty slots that cannot be filled), check cards first.
                #Add card to player's yellow stack.
                for i in range(len(board.dealt[card.deck_id])):
                    if board.dealt[card.deck_id][i] and board.dealt[card.deck_id][i].code == card.code:

                        new_card = None
                        if len(board.decks[card.deck_id]):

                            board_decks = copy(board.decks)
                            deck = copy(board_decks[card.deck_id])

                            random.shuffle(deck)
                            new_card = deck.pop()

                            board_decks[card.deck_id] = deck
                            board.decks = board_decks

                        board_dealt = copy(board.dealt)
                        dealt = copy(board_dealt[card.deck_id])
                        dealt[i] = new_card
                        board_dealt[card.deck_id] = dealt
                        board.dealt = board_dealt

                        agent_cards = copy(agent.cards)
                        yellow_cards = copy(agent_cards['yellow'])
                        yellow_cards.append(card)
                        agent_cards['yellow'] = yellow_cards
                        agent.cards = agent_cards
                    
                        break

        elif 'buy' in action['type']:
            #Decrement player gem stacks by returned_gems. Increment board gem stacks by returned_gems.
            for colour,count in action['returned_gems'].items():

                board_gems = copy(board.gems)
                agent_gems = copy(agent.gems)

                board_gems[colour] += count
                agent_gems[colour] -= count

                board.gems = board_gems
                agent.gems = agent_gems

            #If buying one of the available cards on the board, set removed card slot to new dealt card.
            #Since the board may have None cards (empty slots that cannot be filled), check cards first.
            if 'available' in action['type']:
                for i in range(len(board.dealt[card.deck_id])):
                    if board.dealt[card.deck_id][i] and board.dealt[card.deck_id][i].code == card.code:

                        new_card = None
                        if len(board.decks[card.deck_id]):

                            board_decks = copy(board.decks)
                            deck = copy(board_decks[card.deck_id])

                            random.shuffle(deck)
                            new_card = deck.pop()

                            board_decks[card.deck_id] = deck
                            board.decks = board_decks

                        board_dealt = copy(board.dealt)
                        dealt = copy(board_dealt[card.deck_id])
                        dealt[i] = new_card
                        board_dealt[card.deck_id] = dealt
                        board.dealt = board_dealt

                        break

            #Else, agent is buying a reserved card. Remove card from player's yellow stack.
            else:
                for i in range(len(agent.cards['yellow'])):
                    if agent.cards['yellow'][i].code == card.code:

                        agent_cards = copy(agent.cards)
                        yellow_cards = copy(agent_cards['yellow'])
                        del yellow_cards[i]
                        agent_cards['yellow'] = yellow_cards
                        agent.cards = agent_cards
                   
                        break

            #Add card to player's stack of matching colour, and increment agent's score accordingly.
            agent_cards = copy(agent.cards)
            color_cards = copy(agent_cards[card.colour])
            color_cards.append(card)
            agent_cards[card.colour] = color_cards
            agent.cards = agent_cards

            score += card.points

        if action['noble']:
            #Remove noble from board. Add noble to player's stack. Like cards, nobles aren't hashable due to possessing
            #dictionaries (i.e. resource costs). Therefore, locate and delete the noble via unique code.
            #Add noble's points to agent score.
            for i in range(len(board.nobles)):
                if board.nobles[i][0] == action['noble'][0]:

                    board_nobles = copy(board.nobles)
                    del board_nobles[i]
                    board.nobles = board_nobles

                    agent_nobles = copy(agent.nobles)
                    agent_nobles.append(action['noble'])
                    agent.nobles = agent_nobles

                    score += 3
                    break

        agent.score += score
        agent.passed = (action['type']=='pass')

        agents[agent_id] = agent

        new_state = State(board, agents)

        return new_state

class myAgent(Agent):
    def __init__(self,_id):
        super().__init__(_id)

    def SelectAction(self, actions, game_state):

        exploration_constant = 1/sqrt(2)

        MCTS_AI= MCTS(exploration_constant, game_state, self.id)
        best_action = MCTS_AI.get_action()
        return best_action

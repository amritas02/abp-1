import operator
import logging

import time

from scaii.env.sky_rts.env.scenarios.city_attack import CityAttack
from scaii.env.explanation import Explanation as SkyExplanation, BarChart, BarGroup, Bar

from abp import HRAAdaptive
from abp.explanations import Saliency

logger = logging.getLogger('root')


def alter_q_vals(state, model, step, choice_descriptions, choices, layer_names):
    import numpy as np
    state = np.copy(state)

    #
    for i in range(0,20):
        for j in range(22,40):
            isSet = state[i,j,2] + state[i,j,3] + state[i,j,4] + state[i,j,5]
            if isSet > 0:
                # Big tower
                state[i,j,2] = 0
                state[i,j,3] = 1
                state[i,j,4] = 0
                state[i,j,5] = 0
                # basically no HP
                state[i,j,0] = 5.0 / 70.0
                #Enemy
                state[i,j,6] = 0
                state[i,j,7] = 1
    
    saliency = Saliency(model)
    (_,_,combined) = model.predict(state.flatten())
    combined = combined.data.numpy()

    saliency.generate_saliencies(
        step, state.flatten(),
        choice_descriptions,
        layer_names,
        reshape=state.shape,
        file_path_prefix="fudged_saliencies/")
    
    q_vals = {}
    for choice_idx, _choice in enumerate(choices):
        key = choice_descriptions[choice_idx]
        q_vals[key] = combined[choice_idx]
    
    return  q_vals
    


def run_task(evaluation_config, network_config, reinforce_config):
    env = CityAttack()

    reward_types = sorted(env.reward_types())
    decomposed_rewards = {}

    for type in reward_types:
        decomposed_rewards[type] = 0

    state = env.reset()

    actions = env.actions()['actions']
    actions = sorted(actions.items(), key=operator.itemgetter(1))
    choice_descriptions = list(map(lambda x: x[0], actions))
    choices = list(map(lambda x: x[1], actions))

    # Configure network for reward type
    networks = []
    for reward_type in reward_types:
        name = reward_type
        layers = [{"type": "FC", "neurons": 50}]
        networks.append({"name": name, "layers": layers})

    network_config.networks = networks

    choose_tower = HRAAdaptive(name="tower",
                               choices=choices,
                               reward_types=reward_types,
                               network_config=network_config,
                               reinforce_config=reinforce_config)

    # Training Episodes
    for episode in range(evaluation_config.training_episodes):
        state = env.reset()
        total_reward = 0
        step = 1

        while not state.is_terminal():
            step += 1
            (tower_to_kill,
             q_values,
             combined_q_values) = choose_tower.predict(state.state.flatten())

            action = env.new_action()
            action.attack_quadrant(tower_to_kill)
            action.skip = True
            state = env.act(action)

            for reward_type, reward in state.typed_reward.items():
                choose_tower.reward(reward_type, reward)
                total_reward += reward

        choose_tower.end_episode(state.state.flatten())

        logger.debug("Episode %d : %d, Step: %d" % (episode + 1, total_reward, step))

    choose_tower.disable_learning()

    # Test Episodes
    for episode in range(evaluation_config.test_episodes):
        layer_names = ["HP", "Tank", "Small Bases", "Big Bases", "Big Cities", "Small Cities", "Friend", "Enemy"]

        saliency_explanation = Saliency(choose_tower)

        state = env.reset(visualize=evaluation_config.render, record=True)
        total_reward = 0
        step = 0

        ep_q_vals = []
        ep_fudged_q_vals = []
        while not state.is_terminal():
            step += 1
            explanation = SkyExplanation("Tower Capture", (40, 40))
            (tower_to_kill,
             q_values,
             combined_q_values) = choose_tower.predict(state.state.flatten())

            q_values = q_values.data.numpy()
            combined_q_values = combined_q_values.data.numpy()
            saliencies = saliency_explanation.generate_saliencies(
                step, state.state.flatten(),
                choice_descriptions,
                layer_names,
                reshape=state.state.shape)

            decomposed_q_chart = BarChart("Q Values", "Actions", "QVal By Reward Type")
            q_vals = {}
            for choice_idx, choice in enumerate(choices):
                key = choice_descriptions[choice_idx]
                group = BarGroup("Attack {}".format(key), saliency_key=key)
                explanation.add_layers(layer_names, saliencies["all"], key)
                q_vals[key] = combined_q_values[choice_idx]

                for reward_index, reward_type in enumerate(reward_types):
                    key = "{}_{}".format(choice, reward_type)
                    bar = Bar(reward_type, q_values[reward_index][choice_idx], saliency_key=key)
                    group.add_bar(bar)
                    explanation.add_layers(layer_names, saliencies[reward_type], key=key)

                decomposed_q_chart.add_bar_group(group)

            ep_q_vals.append(q_vals)
            explanation.with_bar_chart(decomposed_q_chart)

            fudged_q_vals = alter_q_vals(state.state, choose_tower, step, choice_descriptions, choices, layer_names)
            ep_fudged_q_vals.append(fudged_q_vals)

            action = env.new_action()
            action.attack_quadrant(tower_to_kill)
            action.skip = True

            state = env.act(action, explanation=explanation)

            time.sleep(0.5)

            total_reward += state.reward

        print("Q vals for ep:", ep_q_vals)
        print("Fudged Q vals for ep:", ep_fudged_q_vals)
        logger.info("End Episode of episode %d with %d steps" % (episode + 1, step))
        logger.info("Total Reward %d!" % (total_reward))

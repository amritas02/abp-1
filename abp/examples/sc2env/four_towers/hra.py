import gym
import time
import numpy as np

from abp import HRAAdaptive
from abp.utils import clear_summary_path
from abp.explanations import PDX
from tensorboardX import SummaryWriter
from gym.envs.registration import register

from sc2env.environments.four_towers_sequential import FourTowersSequentialEnvironment

from absl import app
from absl import flags
from collections import namedtuple
import datetime
import time
import sys
import numpy as np
import pandas as pd
import csv
import json

def run_task(evaluation_config, network_config, reinforce_config):
    import absl
    absl.flags.FLAGS(sys.argv[:1])
    env = FourTowersSequentialEnvironment()

    max_episode_steps = 100
    state = env.reset()
    print('Initial state is: {}'.format(state))
    choices = [0,1,2,3]
    pdx_explanation = PDX()

    reward_types = ['roach', 'zergling', 'damageByRoach', 'damageByZergling', 'damageToRoach', 'damageToZergling']

    agent = HRAAdaptive(name = "FourTowerSequential",
                        choices = choices,
                        reward_types = reward_types,
                        network_config = network_config,
                        reinforce_config = reinforce_config)


    training_summaries_path = evaluation_config.summaries_path + "/train"
    clear_summary_path(training_summaries_path)
    train_summary_writer = SummaryWriter(training_summaries_path)

    test_summaries_path = evaluation_config.summaries_path + "/test"
    clear_summary_path(test_summaries_path)
    test_summary_writer = SummaryWriter(test_summaries_path)

    # Training Episodes
    for episode in range(evaluation_config.training_episodes):
        state = env.reset()
        total_reward = 0
        done = False
        dead = False
        deciding = True
        running = True
        steps = 0
        rewards = []

        initial_state = np.array(state)

        while deciding:
            steps += 1
            action, q_values, combined_q_values = agent.predict(state[0])
            state, reward, done, dead, info = env.step(action)

            while running:
                action = 4
                state, reward, done, dead, info = env.step(action)
                if done:
                    break

            # TODO: Explain the meaning of the numerical constant 200 in this situation
            # eg. MaxPossibleDamage = 200 or RoachZerglingRatio = 200
            if not dead:
                rewards = {
                    'roach': env.decomposed_rewards[len(env.decomposed_rewards) - 1][0],
                    'zergling': env.decomposed_rewards[len(env.decomposed_rewards) - 1][1],
                    'damageByRoach': (-(env.decomposed_rewards[len(env.decomposed_rewards) - 1][2]) / 200),
                    'damageByZergling': (-(env.decomposed_rewards[len(env.decomposed_rewards) - 1][3]) / 200),
                    'damageToRoach': (env.decomposed_rewards[len(env.decomposed_rewards) - 1][4] / 200),
                    'damageToZergling': (env.decomposed_rewards[len(env.decomposed_rewards) - 1][5] / 200)
                }

            else:
                rewards = {
                    'roach': env.decomposed_rewards[len(env.decomposed_rewards) - 2][0],
                    'zergling': env.decomposed_rewards[len(env.decomposed_rewards) - 2][1],
                    'damageByRoach': (-(env.decomposed_rewards[len(env.decomposed_rewards) - 2][2]) / 200),
                    'damageByZergling': (-(env.decomposed_rewards[len(env.decomposed_rewards) - 2][3]) / 200),
                    'damageToRoach': (env.decomposed_rewards[len(env.decomposed_rewards) - 2][4] / 200),
                    'damageToZergling': (env.decomposed_rewards[len(env.decomposed_rewards) - 2][5] / 200)
                }


            for reward_type in rewards.keys():
                agent.reward(reward_type, rewards[reward_type])
                total_reward += rewards[reward_type]

            if dead:
                break

        agent.end_episode(state[0])
        test_summary_writer.add_scalar(tag="Train/Episode Reward", scalar_value=total_reward,
                                       global_step=episode + 1)
        train_summary_writer.add_scalar(tag="Train/Steps to collect all Fruits", scalar_value=steps + 1,
                                        global_step=episode + 1)

        print("EPISODE REWARD {}".format(rewards['roach'] + rewards['zergling']))
        print("EPISODE {}".format(episode))

    # TODO: Display XDAPS

    agent.disable_learning()

    # Test Episodes
    for episode in range(evaluation_config.test_episodes):
        state = env.reset()
        total_reward = 0
        done = False
        steps = 0
        deciding = True
        running = True

        while deciding:
            steps += 1
            action, q_values, combined_q_values = agent.predict(state[0])
            print(action)
            print(q_values)

            if evaluation_config.render:
                # env.render()
                pdx_explanation.render_all_pdx(action, 4, q_values, ['Top_Left', 'Top_Right', 'Bottom_Left', 'Bottom_Right'], ['roach', 'zergling', 'damageByRoach', 'damageByZergling', 'damageToRoach', 'damageToZergling'])
                time.sleep(evaluation_config.sleep)
                # This renders an image of the game and saves to test.jpg
                # imutil.show(self.last_timestep.observation['rgb_screen'], filename="test.jpg")

            state, reward, done, dead, info = env.step(action)

            while running:
                action = 4
                state, reward, done, dead, info = env.step(action)
                if done:
                    break

            if dead:
                break

        agent.end_episode(state)

        test_summary_writer.add_scalar(tag="Test/Episode Reward", scalar_value=total_reward,
                                       global_step=episode + 1)
        test_summary_writer.add_scalar(tag="Test/Steps to collect all Fruits", scalar_value=steps + 1,
                                       global_step=episode + 1)

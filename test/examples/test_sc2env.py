import sys
import unittest

class SC2EnvTests(unittest.TestCase):
    def test_sc2env_four_towers_hra(self):
        sys.argv = ['',
                '--task', 'abp.examples.sc2env.four_towers.hra',
                '--folder', 'test/tasks/sc2env_four_towers_hra']
        from abp.trainer.task_runner import main
        main()

    def test_sc2env_four_towers_multi_unit_hra(self):
        sys.argv = ['',
                '--task', 'abp.examples.sc2env.four_towers_multi_unit.hra',
                '--folder', 'test/tasks/sc2env_four_towers_multi_unit_hra']
        from abp.trainer.task_runner import main
        main()

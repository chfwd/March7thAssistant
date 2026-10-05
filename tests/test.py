import conftest
from module.automation import auto
from tasks.weekly.divergent_universe import DivergentUniverse

from module.logger import log
log.logger.setLevel("DEBUG")
auto._init_input()
# print(auto.find_source_position("./assets/images/screen/divergent_universe/sw_skill.png", "image", None))
# print(auto.find_element("./assets/images/screen/divergent_universe/sw_skill.png", "image", 0.8))
# print(auto.find_element("./assets/images/screen/divergent_universe/sw_skill.png", "image", 0.8, crop=(1600 / 1920, 300 / 1080, 100 / 1920, 100 / 1080)))
d = DivergentUniverse()
print(d.process_random_door())

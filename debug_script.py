import sys
sys.path.append("route_estimator")
sys.path.append("route_estimator/models")
sys.path.append("route_estimator/weather")
sys.path.append("route_estimator/traffic")
from route_estimator import RouteEstimator
from config import Config

simple_model_config = Config()
route_estimator_temp = RouteEstimator(Config())
route_estimator_simple_model = RouteEstimator(simple_model_config, graph=route_estimator_temp.get_graph())
route_estimator_simple_model.activate_energy_model()
route_map_simple_e = route_estimator_simple_model.create_map()

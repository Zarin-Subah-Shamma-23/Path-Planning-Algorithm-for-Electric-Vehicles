import networkx as nx
import osmnx as ox
import geopandas as gpd
import numpy as np
import pandas as pd
from ipyleaflet import *
from shapely.geometry import LineString, mapping
from simple_energy_model import ev_energy_model
from weather import get_weather_data


class RouteEstimator:
    def __init__(self, config, graph=None, use_historical=False):
        self.starting_coord = config.starting_coord
        self.ending_coord = config.ending_coord
        self.google_maps_key = config.google_maps_key
        self.weather_key = config.weather_key
        self.distance = config.distance
        self.edge_weight = config.default_edge_weight
        #used for map compare mode where three lines are drawn
        self.compare_mode = True
        
        self.config = config

        # create an instance of the graph

        if(graph == None):
            if use_historical:
                self.graph = ox.io.load_graphml("logan_elevation.osm")
            else:
                self.create_graph()
        else:
            self.graph = graph
            self.nodes, self.edges =  ox.graph_to_gdfs(self.graph)
        
        # create path layer list
        self.path_layer_list = []

        self.vehicle = ev_energy_model(
            config.vehicle_config['mass'], config.vehicle_config['air_resistance'], config.vehicle_config['area'])

        # create the map from ipyleaflet
        self.m = Map(center=self.starting_coord,
                     basemap=basemaps.CartoDB.Positron, zoom=15)

    def create_map(self):
        # create the TO marker style
        to_marker_style = AwesomeIcon(
            name='circle', icon_color='white', marker_color='red', spin=False)
        # create the two markers
        from_marker = Marker(location=self.starting_coord)
        to_marker = Marker(location=self.ending_coord, icon=to_marker_style)

        from_marker.observe(lambda event: self.handle_change_location(
            event, to_marker), 'location')
        to_marker.observe(lambda event: self.handle_change_location(
            event, from_marker), 'location')
        self.m.add_layer(from_marker)
        self.m.add_layer(to_marker)
        self.set_nearest_node(from_marker)
        self.set_nearest_node(to_marker)
        return self.m

    def create_graph(self):
        graph = ox.graph_from_point(
            self.starting_coord, self.distance, network_type="drive")
        graph = ox.add_edge_speeds(graph)
        graph = ox.add_edge_bearings(graph)
        graph = ox.add_edge_travel_times(graph)
        graph = ox.add_node_elevations_google(graph, self.google_maps_key)
        graph = ox.add_edge_grades(graph)
        self.graph = graph
        # save a dataframe version of edges and nodes for event handler
        self.nodes, self.edges = ox.graph_to_gdfs(self.graph)

    def get_graph(self):
        try:
            return self.graph
        except:
            print("Graph has not been created")

    def get_dataframe_from_graph(self):
        try:
            return ox.graph_to_gdfs(self.graph)
        except:
            print("Graph has not been created")

    def handle_change_location(self, event, marker):
        event_owner = event['owner']
        event_owner.nearest_node = ox.get_nearest_node(
            self.graph, event_owner.location)
        marker.neares_node = ox.get_nearest_node(self.graph, marker.location)
        
        if self.compare_mode:
            self.handle_compare_mode(event_owner.nearest_node, marker.neares_node)
        else:
            
            shortest_path = nx.bellman_ford_path(
                self.graph, event_owner.nearest_node, marker.neares_node, weight=self.edge_weight)

            if len(self.path_layer_list) == 1:
                self.m.remove_layer(self.path_layer_list[0])
                self.path_layer_list.pop()

            shortest_path_points = self.nodes.loc[shortest_path]
            #these edges are all relative to the node, it is not an accurate way to measure the path traversed
            shortest_path_edge_points = self.edges.loc[shortest_path]
            # assign to inner class member
            self.last_shortest_path_nodes = shortest_path_points
            self.last_shortest_path_related_edges = shortest_path_edge_points

            path = gpd.GeoDataFrame(
                [LineString(shortest_path_points.geometry.values)], columns=['geometry'])
            path_layer = GeoData(geo_dataframe=path, style={
                                 'color': 'black', 'weight': 2})
            self.m.add_layer(path_layer)
            self.path_layer_list.append(path_layer)
        
    def handle_compare_mode(self, event_marker, nearest_marker):
        
        if len(self.path_layer_list) == 3:
            self.m.remove_layer(self.path_layer_list[0])
            self.m.remove_layer(self.path_layer_list[1])
            self.m.remove_layer(self.path_layer_list[2])
            self.path_layer_list.pop()
            self.path_layer_list.pop()
            self.path_layer_list.pop()
            
        shortest_path_length = nx.bellman_ford_path(
            self.graph, event_marker, nearest_marker, weight='length')
        shortest_path_time = nx.bellman_ford_path(
            self.graph, event_marker, nearest_marker, weight='travel_time')
        shortest_path_simple_e = nx.bellman_ford_path(
            self.graph, event_marker, nearest_marker, weight='simple_model_e')

        
        length_points = self.nodes.loc[shortest_path_length]
        time_points = self.nodes.loc[shortest_path_time]
        simple_e_points = self.nodes.loc[shortest_path_simple_e]
        

        length_path = path = gpd.GeoDataFrame(
            [LineString(length_points.geometry.values)], columns=['geometry'])
        length_layer = GeoData(geo_dataframe=length_path, style={
                             'color': 'green', 'weight': 2})
        self.m.add_layer(length_layer)
        self.path_layer_list.append(length_layer)


        time_path = path = gpd.GeoDataFrame(
            [LineString(time_points.geometry.values)], columns=['geometry'])
        time_layer = GeoData(geo_dataframe=time_path, style={
                             'color': 'black', 'weight': 2})
        self.m.add_layer(time_layer)
        self.path_layer_list.append(time_layer)
        

        simple_e_path = path = gpd.GeoDataFrame(
            [LineString(simple_e_points.geometry.values)], columns=['geometry'])
        simple_e_layer = GeoData(geo_dataframe=simple_e_path, style={
                             'color': 'red', 'weight': 2})
        self.m.add_layer(simple_e_layer)
        self.path_layer_list.append(simple_e_layer)
        

    def set_nearest_node(self, marker):
        marker.nearest_node = ox.distance.nearest_nodes(
            self.graph, marker.location[0], marker.location[1])
        return

    def activate_energy_model(self):
        self.__activate_simple_energy_model()


    def __activate_simple_energy_model(self):
        # get a dataframe version of the graph to modify
        graphDF = self.get_dataframe_from_graph()

        # placeholder list for new column on the graph
        energy_consumed = []

        # get the starting wind and wind bearing for the energy consumption model
        
        if self.weather_key == 'None':
            f = open('weather_dict.json')
            current_weather = json.load(f)
        else:
            current_weather = get_weather_data(
                self.starting_coord[0], self.starting_coord[1], self.weather_key)

        # For each row, grab the required value, compute the energy, and add to the energy list
        for index, row in graphDF[1].iterrows():
            speed = row['speed_kph']
            bearing = row['bearing']
            grade = row['grade']
            length = row['length']
            wind_speed = current_weather['wind_speed']
            wind_heading = current_weather['wind_heading']
            energy_consumption = self.vehicle.energy_consumption(
                grade, speed/3.6, 0, wind_speed, car_heading=bearing, wind_h=wind_heading, length=length)
            energy_consumed.append(energy_consumption)

        # create a new column on the graphDF
        graphDF[1]['simple_model_e'] = energy_consumed


        # convert df back into graph and assign modified graph to self.graph
        self.graph = ox.graph_from_gdfs(graphDF[0], graphDF[1])

        # update the node, edges objects
        self.nodes, self.edges = ox.graph_to_gdfs(self.graph)

        whole_graph = self.graph.copy()
        totNoEdges = whole_graph.number_of_edges()
        totNoNodes = whole_graph.number_of_nodes()

        listDegree = list(whole_graph.degree())
        Dlist = []
        for j in np.arange(0, len(listDegree)):
            degreeV = listDegree[j][1]
            Dlist.append(degreeV)

        avgDegree = np.sum(Dlist)/totNoNodes

        degree_freq = nx.degree_histogram(whole_graph)
        degrees = range(len(degree_freq))

        density = nx.density(whole_graph)
        diameter = nx.diameter(whole_graph)
        avgPathLength = nx.average_shortest_path_length(whole_graph)
        graph_undirected = whole_graph.to_undirected()
        graph_directed = nx.Graph(graph_undirected)
        avgCC = nx.average_clustering(graph_directed)
        transitivity = nx.transitivity(graph_directed)

    
        random_DF = pd.DataFrame(columns=['Total No of Nodes', 'Total No of Edges', 'Average Degree', 'Density', 'Diameter', 'Average Path Length', 'Average Clustering Coefficient', 'Transitivity', 'Degree Frequency', 'Degrees'])
        random_DF.loc[0, 'Total No of Nodes'] = totNoNodes
        random_DF.loc[0, 'Total No of Edges'] = totNoEdges
        random_DF.loc[0, 'Average Degree'] = avgDegree
        random_DF.loc[0, 'Density'] = density
        random_DF.loc[0, 'Diameter'] = diameter
        random_DF.loc[0, 'Average Path Length'] = avgPathLength
        random_DF.loc[0, 'Average Clustering Coefficient'] = avgCC
        random_DF.loc[0, 'Transitivity'] = transitivity
        random_DF.loc[0, 'Degree Frequency'] = degree_freq
        random_DF.loc[0, 'Degrees'] = degrees

        random_DF.to_csv('graphInfo.csv')
        graphDF[0].to_csv('nodes.csv')
        graphDF[1].to_csv('edges.csv')

        # update the map mode to do shortest path based on the simple energy model
        self.edge_weight = 'simple_model_e'
        

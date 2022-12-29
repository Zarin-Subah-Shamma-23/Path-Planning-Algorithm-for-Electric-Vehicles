from math import sin, radians, cos


class ev_energy_model:
    def __init__(self, mass, air_resistance, area, rf=0.02, air_density=1.225):
        self.mass = mass  # in kilograms かな...
        self.air_resistance = air_resistance
        self.area = area
        self.rolling_friction = rf
        self.air_density = air_density  # kg/m^3
        self.gravity = 9.8

    def energy_consumption(self, angle, v_car, a, v_wind, car_heading=0, wind_h=0, length=1):
        """
        A simple model to predict the instantaneous energy consumption of a vehicle
        Based off of https://www.sciencedirect.com/science/article/pii/S030626191630085X

         Args:
            angle - angle of the car at a certain time point
            v_car - velocity of the car
            a - acceleration of the vehicle
            v_wind - velocity of the wind
            car_h - heading of the car with north being 0 degrees
            wind_h - heading of the wind
         Returns:
            A single value of the total energy cost for the time length

        """

        wind_heading = wind_h
        wind_heading -= car_heading

        wind_speed = v_car - v_wind * cos(radians(wind_heading))

        calc1 = self.mass * a

        calc2 = self.mass * self.gravity * \
            length * (1.75/1000)*(0.0328*v_car+4.575)

        calc3 = 0.5 * self.air_density * self.area * \
            self.air_resistance * (wind_speed ** 2)

        calc4 = self.mass * self.gravity * sin(radians(angle))

        energy = (((calc1 + calc2 + calc3 + calc4) * v_car)/0.92/0.91)

        return energy



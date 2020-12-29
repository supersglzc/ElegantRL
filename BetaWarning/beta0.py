import numpy as np
import numpy.random as rd
# import matplotlib.pyplot as plt

from AgentRun import *

"""
Env1606 alpha_log = -np.log(action_dim) * np.e
ceta3 P=2.0 
ceta1 power__l[0:2]
ceta2 power__l[2:4]
ceta4 power__l[4:6]

EnvNoise 1606
ceta0     for noise_h_std in (0.0, 0.5, 0.1):  # todo

"""


class BeamFormerEnv1000:  # 2020-12-24 stable
    def __init__(self, antennas_num=8, user_num=4,
                 max_power=2., noise_h_std=1., noise_y_std=1.):
        """Down-link Multi-user MIMO beam-forming"""
        self.n = antennas_num
        self.k = user_num
        self.max_power = max_power  # P, max power of Base Station
        self.h_std = 1  # I, std of channel
        self.noise_h_std = noise_h_std  # gamma, std of observed channel noise
        self.noise_y_std = noise_y_std  # sigma, std of received channel noise

        self.func_inv = np.linalg.inv
        self.h_k = None

        self.gamma_r = None
        self.now_step = None
        self.episode_return = None

        '''env information'''
        self.env_name = 'BeamFormerEnv-v0'
        self.state_dim = self.k * self.n
        self.action_dim = self.k * self.n
        self.if_discrete = False
        self.target_reward = 1024
        self.max_step = 2 ** 10

        self.r_offset = self.get__r_offset()  # behind '''env information'''

    def reset(self):
        self.gamma_r = 0.0
        self.now_step = 1
        self.episode_return = 0.0  # Compatibility for ElegantRL 2020-12-21

        state = rd.randn(self.state_dim) * self.h_std
        self.h_k = state.reshape((self.k, self.n))

        state += rd.randn(self.state_dim) * self.noise_h_std
        return state.astype(np.float32)

    def step(self, action):
        w_k = action.reshape((self.k, self.n))
        r_avg = self.get_sinr_rate(w_k, self.h_k)
        r = r_avg - self.r_offset

        self.episode_return += r_avg  # Compatibility for ElegantRL 2020-12-21

        state = rd.randn(self.state_dim) * self.h_std
        self.h_k = state.reshape((self.k, self.n))

        state += rd.randn(self.state_dim) * self.noise_h_std

        done = self.now_step == self.max_step
        self.gamma_r = self.gamma_r * 0.99 + r
        self.now_step += 1
        if done:
            r += self.gamma_r
        return state.astype(np.float32), r, done, {}

    def get_random_action(self):
        w_k = rd.randn(self.k, self.n)
        return self.action__power_limit(w_k, if_max=True)

    def get_traditional_action(self, _state):  # h_k=state
        h_k = self.h_k  # self.h_k = state.reshape((self.k, self.n))
        hh_k = np.dot(h_k.T, h_k)
        # print(f'| traditional solution: hh_k.shape={hh_k.shape}')
        a_k = self.h_std ** 2 + hh_k * (self.max_power / (self.k * self.noise_y_std ** 2))
        # print(f'| traditional solution: a_k.shape={a_k.shape}')

        a_inv = self.func_inv(a_k + np.eye(self.n) * 1e-8)  # avoid ERROR: numpy.linalg.LinAlgError: Singular matrix
        # print(a_inv.shape, np.allclose(np.dot(a_k, a_inv), np.eye(self.n)))
        # print(f'| traditional solution: a_inv.shape={a_inv.shape}')

        a_inv__h_k = np.dot(h_k, a_inv)
        # print(f'| traditional solution: a_inv__h_k.shape={a_inv__h_k.shape}')
        # action_k = a_inv__h_k * (self.max_p / (self.k * np.abs(a_inv__h_k).sum()))
        # print(f'| traditional solution: action_k.shape={action_k.shape}')
        return self.action__power_limit(a_inv__h_k, if_max=True)

    def action__power_limit(self, w_k, if_max=False):  # w_k is action
        # print(f'| Power of BS: {np.power(w_k, 2).sum():.2f}')
        power = np.power(w_k, 2).sum() ** 0.5
        if if_max or power > self.max_power:
            w_k = w_k / (power / self.max_power ** 0.5)

        # power = np.power(w_k, 2).sum() ** 0.5
        # print(f'| Power of BS: {power:.2f}')
        # print(f'| Power of BS: if Power < MaxPower: {power <= self.max_p}')
        return w_k

    def get_sinr_rate(self, w_k, h_k):
        hw_k = (w_k * h_k).sum(axis=1)
        h_w_k = np.dot(w_k, h_k.T).sum(axis=0)
        sinr_k = np.power(hw_k, 2) / (np.power(h_w_k - hw_k, 2) + np.power(self.noise_y_std, 2))
        # print(f'| Signal-to-Interference-and-Noise Ratio (SINR): shape={sinr_k.shape}')

        r_k = np.log(sinr_k + 1)
        # print(f'| rate of each user: shape={r_k.shape}')
        return r_k.mean()

    def get__r_offset(self):
        env = self
        self.r_offset = 0.0

        # # random action
        # _state = env.reset()
        # for i in range(env.max_step):
        #     action = env.get_random_action()
        #     state, reward, done, _ = env.step(action)
        # r_avg__rd = env.episode_return / env.max_step

        # traditional action
        state = env.reset()
        for i in range(env.max_step):
            action = env.get_traditional_action(state)
            state, reward, done, _ = env.step(action)
        r_avg__td = env.episode_return / env.max_step

        # r_offset = (r_avg__rd + r_avg__td) / 2
        # print('| get__r_offset() r_avg__rd, r_avg__td:', r_avg__rd, r_avg__td)
        r_offset = r_avg__td
        return r_offset

    def get_snr_db(self):
        snr = self.max_power / self.noise_y_std ** 2  # P/sigma^2
        return 10 * np.log10(snr)

    def show_information(self):
        print(f"| antennas_num N, user_num K, max_power P: ({self.n}, {self.k}, {self.max_power})\n"
              f"| SNR: {self.get_snr_db()},        channel std h_std: {self.h_std}\n"
              f"| received channel noise noise_y_std: {self.noise_y_std}\n"
              f"| observed channel noise noise_h_std: {self.noise_h_std}\n")
    # def demo0(self, action=None):
    #     w_k = self.get_random_action() if action is None else action  # w_k is action
    #
    #     '''Basic Station (BS)'''
    #     h_k = rd.randn(self.k, self.n) * self.h_std  # h_k is state
    #     print(f'| channel between BS and each user:  shape={h_k.shape}, h_std={self.h_std:.2f}')
    #     s_k = rd.randn(self.k)
    #     print(f'| symbol for each user from BS:      shape={s_k.shape}')
    #     x_n = np.dot(w_k.T, s_k)
    #     print(f'| transmitted signal   from BS:      shape={x_n.shape}')
    #
    #     # ## Tutorial of np.dot and np.matmul
    #     # a = np.ones((2, 3))
    #     # b = rd.rand(3, 4)
    #     # c = np.matmul(a, b) # (np.matmul == np.dot) when both a, b are 1D or 2D matrix
    #     # print(c)
    #     # y_k = [(h_k[i] * x_n).sum() for i in range(self.k)]
    #     # y_k = [np.dot(h_k[i], x_n.T) for i in range(self.k)]
    #     # y_k = [np.dot(x_n, h_k[i].T) for i in range(self.k)]
    #     # y_k = np.dot(h_k, np.expand_dims(x_n, 1)).T
    #     # y_k = np.dot(x_n, h_k.T)
    #     y_k = np.dot(x_n, h_k.T)
    #     print(f'| received signal by each user:      shape={y_k.shape}')
    #     noisy_y_k = y_k + rd.randn(self.k) * self.noise_y_std
    #     print(f'| received signal by each user:      shape={noisy_y_k.shape}, noise_y_std={self.noise_y_std:.2f}')
    #
    #     avg_r = self.get_sinr_rate(w_k, h_k)
    #     print(f'| rate of each user (random action): avg_r={avg_r:.2f}')
    #
    #     '''traditional solution'''
    #     action_k = self.get_traditional_action(h_k)
    #     avg_r = self.get_sinr_rate(action_k, h_k)
    #     print(f'| rate of each user (traditional):   avg_r={avg_r:.2f}')
    #
    #     '''traditional solution: noisy channel'''
    #     noisy_h_k = h_k + rd.randn(self.k, self.n) * self.noise_h_std
    #     action_k = self.get_traditional_action(noisy_h_k)
    #     avg_r = self.get_sinr_rate(action_k, h_k)
    #     print(f'| rate of each user (traditional):   avg_r={avg_r:.2f}, noise_h_std={self.noise_h_std:.2f}')


class BeamFormerEnv1524:  # 2020-12-24
    def __init__(self, antennas_num=8, user_num=4,
                 max_power=2., noise_h_std=1., noise_y_std=1.):
        """Down-link Multi-user MIMO beam-forming"""
        self.n = antennas_num
        self.k = user_num
        self.max_power = max_power  # P, max power of Base Station
        self.h_std = 1  # I, std of channel
        self.noise_h_std = noise_h_std  # gamma, std of observed channel noise
        self.noise_y_std = noise_y_std  # sigma, std of received channel noise

        self.func_inv = np.linalg.inv
        self.h_k = None

        self.gamma_r = None
        self.now_step = None
        self.episode_return = None

        '''env information'''
        self.env_name = 'BeamFormerEnv-v0'
        self.state_dim = self.k * self.n
        self.action_dim = self.k * self.n
        self.if_discrete = False
        self.target_reward = 1024
        self.max_step = 2 ** 10

        self.r_offset = self.get__r_offset()  # behind '''env information'''
        # print(f"| BeamFormerEnv()    self.r_offset: {self.r_offset:.3f}")

    def reset(self):
        self.gamma_r = 0.0
        self.now_step = 1
        self.episode_return = 0.0  # Compatibility for ElegantRL 2020-12-21

        state = rd.randn(self.state_dim) * self.h_std
        self.h_k = state.reshape((self.k, self.n))

        state += rd.randn(self.state_dim) * self.noise_h_std
        return state.astype(np.float32)

    def step(self, action):
        w_k = action.reshape((self.k, self.n))
        r_avg = self.get_sinr_rate(w_k, self.h_k)
        r = r_avg - self.r_offset

        self.episode_return += r_avg  # Compatibility for ElegantRL 2020-12-21

        state = rd.randn(self.state_dim) * self.h_std
        self.h_k = state.reshape((self.k, self.n))

        state += rd.randn(self.state_dim) * self.noise_h_std

        done = self.now_step == self.max_step
        self.gamma_r = self.gamma_r * 0.99 + r
        self.now_step += 1
        if done:
            r += self.gamma_r
            self.episode_return /= self.max_step

        return state.astype(np.float32), r, done, {}

    def get_random_action(self):
        w_k = rd.randn(self.k, self.n)
        return self.action__power_limit(w_k, if_max=True)

    def get_traditional_action(self, _state):  # h_k=state
        h_k = self.h_k  # self.h_k = state.reshape((self.k, self.n))
        hh_k = np.dot(h_k.T, h_k)
        # print(f'| traditional solution: hh_k.shape={hh_k.shape}')
        a_k = self.h_std ** 2 + hh_k * (self.max_power / (self.k * self.noise_y_std ** 2))
        # print(f'| traditional solution: a_k.shape={a_k.shape}')

        a_inv = self.func_inv(a_k + np.eye(self.n) * 1e-8)  # avoid ERROR: numpy.linalg.LinAlgError: Singular matrix
        # print(a_inv.shape, np.allclose(np.dot(a_k, a_inv), np.eye(self.n)))
        # print(f'| traditional solution: a_inv.shape={a_inv.shape}')

        a_inv__h_k = np.dot(h_k, a_inv)
        # print(f'| traditional solution: a_inv__h_k.shape={a_inv__h_k.shape}')
        # action_k = a_inv__h_k * (self.max_p / (self.k * np.abs(a_inv__h_k).sum()))
        # print(f'| traditional solution: action_k.shape={action_k.shape}')
        return self.action__power_limit(a_inv__h_k, if_max=True)

    def action__power_limit(self, w_k, if_max=False):  # w_k is action
        # print(f'| Power of BS: {np.power(w_k, 2).sum():.2f}')
        power = np.power(w_k, 2).sum() ** 0.5
        if if_max or power > self.max_power:
            w_k = w_k / (power / self.max_power ** 0.5)

        # power = np.power(w_k, 2).sum() ** 0.5
        # print(f'| Power of BS: {power:.2f}')
        # print(f'| Power of BS: if Power < MaxPower: {power <= self.max_p}')
        return w_k

    def get_sinr_rate(self, w_k, h_k):
        hw_k = (w_k * h_k).sum(axis=1)
        h_w_k = np.dot(w_k, h_k.T).sum(axis=0)
        sinr_k = np.power(hw_k, 2) / (np.power(h_w_k - hw_k, 2) + np.power(self.noise_y_std, 2))
        # print(f'| Signal-to-Interference-and-Noise Ratio (SINR): shape={sinr_k.shape}')

        r_k = np.log(sinr_k + 1)
        # print(f'| rate of each user: shape={r_k.shape}')
        return r_k.mean()

    def get__r_offset(self):
        env = self
        self.r_offset = 0.0

        # # random action
        # _state = env.reset()
        # for i in range(env.max_step):
        #     action = env.get_random_action()
        #     state, reward, done, _ = env.step(action)
        # r_avg__rd = env.episode_return

        # traditional action
        state = env.reset()
        for i in range(env.max_step):
            action = env.get_traditional_action(state)
            state, reward, done, _ = env.step(action)
        r_avg__td = env.episode_return

        # r_offset = (r_avg__rd + r_avg__td) / 2
        # print('| get__r_offset() r_avg__rd, r_avg__td:', r_avg__rd, r_avg__td)
        r_offset = r_avg__td
        return r_offset

    def get_snr_db(self):
        snr = self.max_power / self.noise_y_std ** 2  # P/sigma^2
        return 10 * np.log10(snr)

    def show_information(self):
        print(f"| antennas_num N, user_num K, max_power P: ({self.n}, {self.k}, {self.max_power})\n"
              f"| SNR: {self.get_snr_db()},        channel std h_std: {self.h_std}\n"
              f"| received channel noise noise_y_std: {self.noise_y_std}\n"
              f"| observed channel noise noise_h_std: {self.noise_h_std}\n")
    # def demo0(self, action=None):
    #     w_k = self.get_random_action() if action is None else action  # w_k is action
    #
    #     '''Basic Station (BS)'''
    #     h_k = rd.randn(self.k, self.n) * self.h_std  # h_k is state
    #     print(f'| channel between BS and each user:  shape={h_k.shape}, h_std={self.h_std:.2f}')
    #     s_k = rd.randn(self.k)
    #     print(f'| symbol for each user from BS:      shape={s_k.shape}')
    #     x_n = np.dot(w_k.T, s_k)
    #     print(f'| transmitted signal   from BS:      shape={x_n.shape}')
    #
    #     # ## Tutorial of np.dot and np.matmul
    #     # a = np.ones((2, 3))
    #     # b = rd.rand(3, 4)
    #     # c = np.matmul(a, b) # (np.matmul == np.dot) when both a, b are 1D or 2D matrix
    #     # print(c)
    #     # y_k = [(h_k[i] * x_n).sum() for i in range(self.k)]
    #     # y_k = [np.dot(h_k[i], x_n.T) for i in range(self.k)]
    #     # y_k = [np.dot(x_n, h_k[i].T) for i in range(self.k)]
    #     # y_k = np.dot(h_k, np.expand_dims(x_n, 1)).T
    #     # y_k = np.dot(x_n, h_k.T)
    #     y_k = np.dot(x_n, h_k.T)
    #     print(f'| received signal by each user:      shape={y_k.shape}')
    #     noisy_y_k = y_k + rd.randn(self.k) * self.noise_y_std
    #     print(f'| received signal by each user:      shape={noisy_y_k.shape}, noise_y_std={self.noise_y_std:.2f}')
    #
    #     avg_r = self.get_sinr_rate(w_k, h_k)
    #     print(f'| rate of each user (random action): avg_r={avg_r:.2f}')
    #
    #     '''traditional solution'''
    #     action_k = self.get_traditional_action(h_k)
    #     avg_r = self.get_sinr_rate(action_k, h_k)
    #     print(f'| rate of each user (traditional):   avg_r={avg_r:.2f}')
    #
    #     '''traditional solution: noisy channel'''
    #     noisy_h_k = h_k + rd.randn(self.k, self.n) * self.noise_h_std
    #     action_k = self.get_traditional_action(noisy_h_k)
    #     avg_r = self.get_sinr_rate(action_k, h_k)
    #     print(f'| rate of each user (traditional):   avg_r={avg_r:.2f}, noise_h_std={self.noise_h_std:.2f}')


class BeamFormerEnvNoisy:  # 2020-12-24
    def __init__(self, antennas_num=8, user_num=4,
                 max_power=1., noise_h_std=1., noise_y_std=1.):
        """Down-link Multi-user MIMO beam-forming"""
        self.n = antennas_num
        self.k = user_num
        self.max_power = max_power  # P, max power of Base Station
        self.h_std = 1  # I, std of channel
        self.noise_h_std = noise_h_std  # gamma, std of observed channel noise
        self.noise_y_std = noise_y_std  # sigma, std of received channel noise

        self.func_inv = np.linalg.inv
        self.h_k = None

        self.gamma_r = None
        self.now_step = None
        self.episode_return = None

        '''env information'''
        self.env_name = 'BeamFormerEnv-v0'
        self.state_dim = self.k * self.n
        self.action_dim = self.k * self.n
        self.if_discrete = False
        self.target_reward = 1024
        self.max_step = 2 ** 10

        self.r_offset = self.get__r_offset()  # behind '''env information'''
        # print(f"| BeamFormerEnv()    self.r_offset: {self.r_offset:.3f}")

    def reset(self):
        self.gamma_r = 0.0
        self.now_step = 1
        self.episode_return = 0.0  # Compatibility for ElegantRL 2020-12-21

        state = rd.randn(self.state_dim) * self.h_std
        self.h_k = state.reshape((self.k, self.n))

        state += rd.randn(self.state_dim) * self.noise_h_std
        return state.astype(np.float32)

    def step(self, action):
        w_k = action.reshape((self.k, self.n))
        r_avg = self.get_sinr_rate(w_k, self.h_k)
        r = r_avg - self.r_offset

        self.episode_return += r_avg  # Compatibility for ElegantRL 2020-12-21

        state = rd.randn(self.state_dim) * self.h_std
        self.h_k = state.reshape((self.k, self.n))

        state += rd.randn(self.state_dim) * self.noise_h_std

        done = self.now_step == self.max_step
        self.gamma_r = self.gamma_r * 0.99 + r
        self.now_step += 1
        if done:
            r += self.gamma_r
            self.episode_return /= self.max_step

        return state.astype(np.float32), r, done, {}

    def get_random_action(self):
        w_k = rd.randn(self.k, self.n)
        return self.action__power_limit(w_k, if_max=True)

    def get_traditional_action(self, _state):  # h_k=state
        h_k = self.h_k  # self.h_k = state.reshape((self.k, self.n))
        hh_k = np.dot(h_k.T, h_k)
        # print(f'| traditional solution: hh_k.shape={hh_k.shape}')
        a_k = self.h_std ** 2 + hh_k * (self.max_power / (self.k * self.noise_y_std ** 2))
        # print(f'| traditional solution: a_k.shape={a_k.shape}')

        a_inv = self.func_inv(a_k + np.eye(self.n) * 1e-8)  # avoid ERROR: numpy.linalg.LinAlgError: Singular matrix
        # print(a_inv.shape, np.allclose(np.dot(a_k, a_inv), np.eye(self.n)))
        # print(f'| traditional solution: a_inv.shape={a_inv.shape}')

        a_inv__h_k = np.dot(h_k, a_inv)
        # print(f'| traditional solution: a_inv__h_k.shape={a_inv__h_k.shape}')
        # action_k = a_inv__h_k * (self.max_p / (self.k * np.abs(a_inv__h_k).sum()))
        # print(f'| traditional solution: action_k.shape={action_k.shape}')
        return self.action__power_limit(a_inv__h_k, if_max=True)

    def action__power_limit(self, w_k, if_max=False):  # w_k is action
        # print(f'| Power of BS: {np.power(w_k, 2).sum():.2f}')
        power = np.power(w_k, 2).sum() ** 0.5
        if if_max or power > self.max_power:
            w_k = w_k / (power / self.max_power ** 0.5)

        # power = np.power(w_k, 2).sum() ** 0.5
        # print(f'| Power of BS: {power:.2f}')
        # print(f'| Power of BS: if Power < MaxPower: {power <= self.max_p}')
        return w_k

    def get_sinr_rate(self, w_k, h_k):
        hw_k = (w_k * h_k).sum(axis=1)
        h_w_k = np.dot(w_k, h_k.T).sum(axis=0)
        sinr_k = np.power(hw_k, 2) / (np.power(h_w_k - hw_k, 2) + np.power(self.noise_y_std, 2))
        # print(f'| Signal-to-Interference-and-Noise Ratio (SINR): shape={sinr_k.shape}')

        r_k = np.log(sinr_k + 1)
        # print(f'| rate of each user: shape={r_k.shape}')
        return r_k.mean()

    def get__r_offset(self):
        env = self
        self.r_offset = 0.0

        # # random action
        # _state = env.reset()
        # for i in range(env.max_step):
        #     action = env.get_random_action()
        #     state, reward, done, _ = env.step(action)
        # r_avg__rd = env.episode_return

        # traditional action
        state = env.reset()
        for i in range(env.max_step):
            action = env.get_traditional_action(state)
            state, reward, done, _ = env.step(action)
        r_avg__td = env.episode_return

        # r_offset = (r_avg__rd + r_avg__td) / 2
        # print('| get__r_offset() r_avg__rd, r_avg__td:', r_avg__rd, r_avg__td)
        r_offset = r_avg__td
        return r_offset

    def get_snr_db(self):
        snr = self.max_power / self.noise_y_std ** 2  # P/sigma^2
        return 10 * np.log10(snr)

    def show_information(self):
        print(f"| antennas_num N, user_num K, max_power P: ({self.n}, {self.k}, {self.max_power})\n"
              f"| SNR: {self.get_snr_db()},        channel std h_std: {self.h_std}\n"
              f"| received channel noise noise_y_std: {self.noise_y_std}\n"
              f"| observed channel noise noise_h_std: {self.noise_h_std}\n")
    # def demo0(self, action=None):
    #     w_k = self.get_random_action() if action is None else action  # w_k is action
    #
    #     '''Basic Station (BS)'''
    #     h_k = rd.randn(self.k, self.n) * self.h_std  # h_k is state
    #     print(f'| channel between BS and each user:  shape={h_k.shape}, h_std={self.h_std:.2f}')
    #     s_k = rd.randn(self.k)
    #     print(f'| symbol for each user from BS:      shape={s_k.shape}')
    #     x_n = np.dot(w_k.T, s_k)
    #     print(f'| transmitted signal   from BS:      shape={x_n.shape}')
    #
    #     # ## Tutorial of np.dot and np.matmul
    #     # a = np.ones((2, 3))
    #     # b = rd.rand(3, 4)
    #     # c = np.matmul(a, b) # (np.matmul == np.dot) when both a, b are 1D or 2D matrix
    #     # print(c)
    #     # y_k = [(h_k[i] * x_n).sum() for i in range(self.k)]
    #     # y_k = [np.dot(h_k[i], x_n.T) for i in range(self.k)]
    #     # y_k = [np.dot(x_n, h_k[i].T) for i in range(self.k)]
    #     # y_k = np.dot(h_k, np.expand_dims(x_n, 1)).T
    #     # y_k = np.dot(x_n, h_k.T)
    #     y_k = np.dot(x_n, h_k.T)
    #     print(f'| received signal by each user:      shape={y_k.shape}')
    #     noisy_y_k = y_k + rd.randn(self.k) * self.noise_y_std
    #     print(f'| received signal by each user:      shape={noisy_y_k.shape}, noise_y_std={self.noise_y_std:.2f}')
    #
    #     avg_r = self.get_sinr_rate(w_k, h_k)
    #     print(f'| rate of each user (random action): avg_r={avg_r:.2f}')
    #
    #     '''traditional solution'''
    #     action_k = self.get_traditional_action(h_k)
    #     avg_r = self.get_sinr_rate(action_k, h_k)
    #     print(f'| rate of each user (traditional):   avg_r={avg_r:.2f}')
    #
    #     '''traditional solution: noisy channel'''
    #     noisy_h_k = h_k + rd.randn(self.k, self.n) * self.noise_h_std
    #     action_k = self.get_traditional_action(noisy_h_k)
    #     avg_r = self.get_sinr_rate(action_k, h_k)
    #     print(f'| rate of each user (traditional):   avg_r={avg_r:.2f}, noise_h_std={self.noise_h_std:.2f}')


def simulate_random(sim_times=2 ** 18, antennas_num=20, user_num=10,
                    max_power=2., noise_h_std=1., noise_y_std=1.):
    # print(f'Random')
    env = BeamFormerEnv1524(antennas_num, user_num, max_power, noise_h_std, noise_y_std)
    # env.show_information()

    sim_times1 = int(sim_times ** 0.5)
    sim_times2 = int(sim_times / sim_times1)

    import tqdm
    t = tqdm.trange(sim_times1, desc='Random avgR')

    reward_sum1 = 0.0

    for i in t:
        reward_sum2 = 0.0

        _state = env.reset()
        for _ in range(sim_times2):
            action = env.get_random_action()  # env.get_traditional_action(state)
            next_state, reward, done, _ = env.step(action)
            reward_sum2 += reward
            # state = next_state

        reward_avg2 = reward_sum2 / sim_times2
        reward_sum1 += reward_avg2

        t.set_description(f"Random avgR: {reward_sum1 / (i + 1):.4f}", refresh=True)
    reward_avg1 = reward_sum1 / sim_times1
    # print(f"Random avgR: {reward_avg1:.4f}, SNR: {env.get_snr_db()} dB")
    return reward_avg1


def simulate_traditional(sim_times=2 ** 18, antennas_num=20, user_num=10,
                         max_power=2., noise_h_std=1., noise_y_std=1.):
    # print(f'Traditional')
    env = BeamFormerEnv1524(antennas_num, user_num, max_power, noise_h_std, noise_y_std)
    # env.show_information()

    sim_times1 = int(sim_times ** 0.5)
    sim_times2 = int(sim_times / sim_times1)

    import tqdm
    t = tqdm.trange(sim_times1, desc='Traditional avgR')

    reward_sum1 = 0.0

    for i in t:
        reward_sum2 = 0.0

        state = env.reset()
        for _ in range(sim_times2):
            action = env.get_traditional_action(state)
            next_state, reward, done, _ = env.step(action)
            reward_sum2 += reward
            state = next_state

        reward_avg2 = reward_sum2 / sim_times2
        reward_sum1 += reward_avg2

        t.set_description(f"Traditional avgR: {reward_sum1 / (i + 1):.4f}", refresh=True)
    reward_avg1 = reward_sum1 / sim_times1
    # print(f"Traditional avgR: {reward_avg1:.4f}, SNR: {env.get_snr_db()} dB")
    return reward_avg1


def run__plan():
    env = BeamFormerEnv1524()

    state = env.reset()
    r_sum = 0.0
    for i in range(env.max_step):
        action = env.get_traditional_action(state)
        state, reward, done, _ = env.step(action)
        r_sum += reward
    print(';', r_sum)

    exit()
    sim_times = 2 ** 16
    noise_y_std = 1.0
    noise_h_std = 1.0

    snr_db_l = np.linspace(-10, 20, 13)
    power__l = 10 ** (snr_db_l / 10) * (noise_y_std ** 2)

    recorder = list()

    for antennas_num, user_num in ((20, 10), (20, 5), (10, 5), (10, 10)):
        for max_power in power__l:
            # r = simulate_traditional(sim_times, antennas_num, user_num, max_power, noise_h_std, noise_y_std)
            r = simulate_random(sim_times, antennas_num, user_num, max_power, noise_h_std, noise_y_std)
            recorder.append(r)

    save_npy = 'beta0-y_std-0.5--h_std-1.0.npy'
    np.save(save_npy, recorder, )
    print('| Saved:', save_npy)


def train__rl():
    env = BeamFormerEnv1524()

    from AgentZoo import AgentModSAC

    args = Arguments(rl_agent=AgentModSAC, env=env, gpu_id=0)
    args.break_step = int(6e4 * 8)  # UsedTime: 900s (reach target_reward 200)
    args.net_dim = 2 ** 7
    args.init_for_training()
    train_agent_mp(args)  # train_agent(args)


if __name__ == '__main__':
    # run__plan()
    # read_print_terminal_data()
    # read_print_terminal_data1()
    train__rl()

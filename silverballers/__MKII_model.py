"""
@Author: Conghao Wong
@Date: 2022-06-22 09:58:48
@LastEditors: Conghao Wong
@LastEditTime: 2023-10-11 10:44:50
@Description: file content
@Github: https://github.com/cocoon2wong
@Copyright 2022 Conghao Wong, All Rights Reserved.
"""

import tensorflow as tf

from ..__root import BaseObject
from ..args import Args
from ..constant import ANN_TYPES, INPUT_TYPES, INTERPOLATION_TYPES
from ..dataset import AnnotationManager
from ..model import Model
from ..training import Structure
from .__agentModel import AgentArgs, BaseAgentModel, BaseAgentStructure
from .__baseArgs import SilverballersArgs
from .__handlerModel import BaseHandlerModel, BaseHandlerStructure
from .__MKII_utils import SILVERBALLERS_DICT


class SilverballersModel(Model):
    """
    SilverballersModel
    ---
    The two-stage silverballers model.
    NOTE: This model is typically used for testing, not training.
    The SilverballersModel itself is not trainable. It only serves 
    as a container that provides a running environment for different 
    agent and handler sub-networks.

    Member Managers
    ---
    - (Soft member) Stage-1 Subnetwork, type is `BaseAgentModel`
        or a subclass of it;
    - (Soft member) Stage-2 Subnetwork, type is `BaseHandlerModel`
        or a subclass of it.
    """

    def __init__(self, Args: SilverballersArgs,
                 agentModel: BaseAgentModel,
                 handlerModel: BaseHandlerModel = None,
                 structure=None,
                 *args, **kwargs):

        super().__init__(Args, structure, *args, **kwargs)

        self.args: SilverballersArgs
        self.manager: Structure

        # Processes are applied in AgentModels and HandlerModels
        self.set_preprocess()

        # Layers
        self.agent = agentModel
        self.handler = handlerModel

        # Set model inputs
        a_type = self.agent.input_types
        h_type = self.handler.input_types[:-1]
        self.input_types = list(set(a_type + h_type))

        # Make sure that obs trajs are the first model input
        if ((t := INPUT_TYPES.OBSERVED_TRAJ) in self.input_types and
                self.input_types[0] != t):
            self.input_types.remove(t)
            self.input_types = [t] + self.input_types

        self.agent_input_index = self.get_input_index(a_type)
        self.handler_input_index = self.get_input_index(h_type)

        # Extra model outputs
        self.ext_traj_wise_outputs = self.handler.ext_traj_wise_outputs
        self.ext_agent_wise_outputs = self.handler.ext_agent_wise_outputs

    def get_input_index(self, input_type: list[str]):
        return [self.input_types.index(t) for t in input_type]

    def call(self, inputs: list[tf.Tensor],
             training=None, mask=None,
             *args, **kwargs):

        # Prepare model inputs
        traj_index = self.agent_input_index[0]

        # Predict with `co2bb` (Coordinates to 2D bounding boxes)
        if self.args.force_anntype == ANN_TYPES.BB_2D and \
           self.agent.args.anntype == ANN_TYPES.CO_2D and \
           self.manager.split_manager.anntype == ANN_TYPES.BB_2D:

            # Flatten into a series of 2D points
            all_trajs = self.manager.get_member(AnnotationManager) \
                .target.get_coordinate_series(inputs[traj_index])

        else:
            all_trajs = [inputs[traj_index]]

        ######################
        # Stage-1 Subnetwork #
        ######################
        y_all_agent = []
        y_agent = []
        for traj in all_trajs:
            # Call the first stage model multiple times
            x_agent = [traj] + [inputs[i] for i in self.agent_input_index[1:]]
            y_all_agent.append(o := self.agent.implement(x_agent))
            y_agent.append(o[0])

        y_agent = tf.concat(y_agent, axis=-1)

        # Down sampling from K*Kc generations (if needed)
        if self.args.down_sampling_rate < 1.0:
            K_current = y_agent.shape[-3]
            K_new = K_current * self.args.down_sampling_rate
            new_index = tf.random.shuffle(tf.range(K_current))[:int(K_new)]
            y_agent = tf.gather(y_agent, new_index, axis=-3)

        ######################
        # Stage-2 Subnetwork #
        ######################
        x_handler = [inputs[i] for i in self.handler_input_index]
        x_handler.append(y_agent)
        y_handler = self.handler.forward(x_handler)

        if not training and (c := self.args.channel) != -1:
            y_handler[0] = y_handler[0][..., c, tf.newaxis, :, :]

        return [y_handler[0]] + y_all_agent + [y_handler]

    def print_info(self, **kwargs):
        info = {'Indices of future keypoints': self.agent.key_indices_future,
                'Indices of past keypoints': self.agent.key_indices_past,
                'Stage-1 Subnetwork': f"'{self.agent.name}' from '{self.structure.args.loada}'",
                'Stage-2 Subnetwork': f"'{self.handler.name}' from '{self.structure.args.loadb}'"}

        kwargs_old = kwargs.copy()
        kwargs.update(**info)
        super().print_info(**kwargs)

        self.agent.print_info(**kwargs_old)
        self.handler.print_info(**kwargs_old)


class SilverballersMKII(Structure):
    """
    SilverballersMKII Structure
    ---
    Basic structure to run the `agent-handler` based silverballers model.
    NOTE: It is only used for TESTING silverballers models, not training.

    Member Managers
    ---
    - Stage-1 Subnetwork Manager, type is `BaseAgentStructure` or its subclass;
    - Stage-2 Subnetwork Manager, type is `BaseHandlerStructure` or its subclass;
    - All members from the `Structure`.
    """

    AGENT_STRUCTURE_TYPE = BaseAgentStructure
    HANDLER_STRUCTURE_TYPE = BaseHandlerStructure

    def __init__(self, terminal_args: list[str]):

        min_args = SilverballersArgs(terminal_args, is_temporary=True)
        a_model_path = min_args.loada
        b_model_path = min_args.loadb

        # Assign the model type of the first-stage subnetwork
        min_args_a = Args(is_temporary=True)._load_from_json(a_model_path)
        agent_model_type = SILVERBALLERS_DICT.get_model(min_args_a.model)
        agent_struct_type = SILVERBALLERS_DICT.get_structure(min_args_a.model)

        # Assign the model type of the second-stage subnetwork
        interp_model = INTERPOLATION_TYPES.get_type(b_model_path)
        if interp_model is None:
            min_args_b = Args(is_temporary=True)._load_from_json(b_model_path)
            interp_model = min_args_b.model

        handler_model_type = SILVERBALLERS_DICT.get_model(interp_model)
        handler_structure_type = SILVERBALLERS_DICT.get_structure(
            interp_model)

        # Assign types of all subnetworks
        self.agent_model_type = agent_model_type
        self.handler_model_type = handler_model_type
        if agent_struct_type:
            self.AGENT_STRUCTURE_TYPE = agent_struct_type

        if handler_structure_type:
            self.HANDLER_STRUCTURE_TYPE = handler_structure_type

        # Init log-related functions
        BaseObject.__init__(self)

        # Load minimal args
        min_args = SilverballersArgs(terminal_args, is_temporary=True)

        # Check args
        if 'null' in [min_args.loada, min_args.loadb]:
            self.log('`Agent` or `Handler` model not found!' +
                     ' Please specific their paths via `--loada` (`-la`)' +
                     ' or `--loadb` (`-lb`).',
                     level='error', raiseError=KeyError)

        # Load basic args from the saved agent model
        min_args_a = AgentArgs(terminal_args + ['--load', min_args.loada],
                               is_temporary=True)

        # Assign args from the saved Agent-Model's args
        extra_args = []
        if min_args.batch_size > min_args_a.batch_size:
            extra_args += ['--batch_size', str(min_args_a.batch_size)]

        # Check if predict trajectories recurrently
        if 'pred_frames' not in min_args._args_runnning.keys():
            extra_args += ['--pred_frames', str(min_args_a.pred_frames)]
        else:
            if not min_args_a.deterministic:
                self.log('Predict trajectories currently is currently not ' +
                         'supported with generative models.',
                         level='error', raiseError=NotImplementedError)

            if min_args.pred_interval == -1:
                self.log('Please set the prediction interval when you want ' +
                         'to make recurrent predictions. Current prediction' +
                         f' interval is `{min_args.pred_interval}`.',
                         level='error', raiseError=ValueError)

        extra_args += ['--split', str(min_args_a.split),
                       '--anntype', str(min_args_a.anntype),
                       '--obs_frames', str(min_args_a.obs_frames),
                       '--interval', str(min_args_a.interval),
                       '--model_type', str(min_args_a.model_type)]

        self.args: SilverballersArgs = SilverballersArgs(
            terminal_args + extra_args)

        if self.args.force_anntype != 'null':
            self.args._set('anntype', self.args.force_anntype)

        # init the structure
        super().__init__(self.args)

        if (k := '--force_anntype') in terminal_args:
            terminal_args.remove(k)

        self.noTraining = True

        # config second-stage model
        if self.handler_model_type.is_interp_handler:
            handler_args = None
        else:
            handler_args = terminal_args + ['--load', self.args.loadb]

        # First-stage subnetwork
        agent_args = self.AGENT_STRUCTURE_TYPE.ARG_TYPE(
            terminal_args + ['--load', self.args.loada],
            is_temporary=True)
        self.agent = self.AGENT_STRUCTURE_TYPE(agent_args, manager=self)
        self.agent.set_model_type(self.agent_model_type)
        self.agent.model = self.agent.create_model()
        self.agent.model.load_weights_from_logDir(self.args.loada)

        # Second-stage subnetwork
        handler_args = self.HANDLER_STRUCTURE_TYPE.ARG_TYPE(handler_args,
                                                            is_temporary=True)
        handler_args._set('key_points', self.agent.args.key_points)
        self.handler = self.HANDLER_STRUCTURE_TYPE(handler_args, self)
        self.handler.set_model_type(self.handler_model_type)
        self.handler.model = self.handler.create_model(as_single_model=False)
        if not self.handler_model_type.is_interp_handler:
            self.handler.model.load_weights_from_logDir(self.args.loadb)

        # set labels
        self.set_labels(INPUT_TYPES.GROUNDTRUTH_TRAJ)

    def create_model(self, *args, **kwargs):
        return SilverballersModel(
            self.args,
            agentModel=self.agent.model,
            handlerModel=self.handler.model,
            structure=self,
            *args, **kwargs)

    def print_test_results(self, loss_dict: dict[str, float], **kwargs):
        super().print_test_results(loss_dict, **kwargs)
        self.log(f'Test with 1st sub-network `{self.args.loada}` ' +
                 f'and 2nd seb-network `{self.args.loadb}` done.')


SILVERBALLERS_DICT.register(MKII=[SilverballersMKII, None])

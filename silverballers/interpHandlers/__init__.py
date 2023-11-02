"""
@Author: Conghao Wong
@Date: 2022-11-28 21:29:49
@LastEditors: Conghao Wong
@LastEditTime: 2023-11-02 18:19:37
@Description: file content
@Github: https://github.com/cocoon2wong
@Copyright 2022 Conghao Wong, All Rights Reserved.
"""

from ...constant import INTERPOLATION_TYPES
from .__linear import (LinearAccHandlerModel, LinearHandlerModel,
                       LinearSpeedHandlerModel)
from .__newton import NewtonHandlerModel

INTERPOLATION_HANDLER_DICT: dict = {
    INTERPOLATION_TYPES.LINEAR: [None, LinearHandlerModel],
    INTERPOLATION_TYPES.LINEAR_SPEED: [None, LinearSpeedHandlerModel],
    INTERPOLATION_TYPES.LINEAR_ACC: [None, LinearAccHandlerModel],
    INTERPOLATION_TYPES.NEWTON: [None, NewtonHandlerModel],
}

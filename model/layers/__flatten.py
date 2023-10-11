"""
@Author: Conghao Wong
@Date: 2023-06-15 15:28:10
@LastEditors: Conghao Wong
@LastEditTime: 2023-10-10 20:21:00
@Description: file content
@Github: https://cocoon2wong.github.io
@Copyright 2023 Conghao Wong, All Rights Reserved.
"""

import torch


class Flatten(torch.nn.Module):

    def __init__(self, axes_num: int, *args, **kwargs):
        """
        Flatten the input on the given number of axes.
        It will flatten values in the last `axes_num` axes.
        For example, when `axes_num=2`, it outputs a tensor
        with shape `(a, b, c*d)` for the input tensor with
        shape `(a, b, c, d)`.
        """
        super().__init__(*args, **kwargs)
        self.n = axes_num

    def forward(self, inputs, *args, **kwargs):
        s = list(inputs.shape)
        o = torch.reshape(inputs, s[:-self.n] + [-1])
        return o

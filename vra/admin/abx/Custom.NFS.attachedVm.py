# -*- coding: utf-8 -*-
'''
@copyright: Equal Plus
@author: Hye-Churn Jang
'''

#===============================================================================
# Import Libraries Here
#===============================================================================


#===============================================================================
# Implement Handler Here
#===============================================================================
def handler(context, inputs):
    vms = inputs['vms']
    inputs['attachedVm'] = vms
    outputs = inputs
    outputs.pop('vms')
    return outputs

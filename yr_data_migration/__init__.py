# -*- coding: utf-8 -*-
from . import models
from . import wizard


def _post_init_hook(env):
    # the tills that exist when the module is installed ask for the seller before payment
    env['pos.config'].with_context(active_test=False).search([]).write({'yr_seller_mode': 'required'})

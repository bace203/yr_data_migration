# -*- coding: utf-8 -*-
from odoo import api, fields, models

SELLER_MODES = [
    ('none', 'Non demandé'),
    ('optional', 'Demandé, facultatif'),
    ('required', 'Obligatoire'),
]


class PosConfig(models.Model):
    _inherit = 'pos.config'

    yr_seller_mode = fields.Selection(
        SELLER_MODES, 'Vendeur avant paiement', default='none', required=True,
        help='En caisse, au clic sur « Paiement », la liste des vendeurs s\'ouvre pour choisir qui a servi le '
             'client (le caissier reste l\'utilisateur connecté).')
    yr_seller_employee_ids = fields.Many2many(
        'hr.employee', 'pos_config_yr_seller_rel', 'config_id', 'employee_id', 'Vendeurs',
        help='Vendeurs proposés dans cette caisse. Vide : tous les employés de la société.')
    yr_seller_data = fields.Json(compute='_compute_yr_seller_data')

    @api.depends('yr_seller_mode', 'yr_seller_employee_ids', 'company_id')
    def _compute_yr_seller_data(self):
        for config in self:
            employees = config.yr_seller_employee_ids.sudo()
            if config.yr_seller_mode != 'none' and not employees:
                employees = self.env['hr.employee'].sudo().search(
                    [('company_id', 'in', [config.company_id.id, False])], order='name')
            config.yr_seller_data = [{'id': e.id, 'name': e.name}
                                     for e in employees.filtered('active').sorted('name')]


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    pos_yr_seller_mode = fields.Selection(related='pos_config_id.yr_seller_mode', readonly=False)
    pos_yr_seller_employee_ids = fields.Many2many(related='pos_config_id.yr_seller_employee_ids', readonly=False)

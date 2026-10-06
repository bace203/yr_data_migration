# -*- coding: utf-8 -*-
"""History of the fastmag imports: what was imported, how far, and where an interrupted import resumes."""
from odoo import fields, models


class YrMigrationLog(models.Model):
    _name = 'yr.migration.log'
    _description = 'Import fastmag (historique)'
    _order = 'id desc'

    name = fields.Char('Fichier', required=True)
    file_hash = fields.Char('Empreinte du fichier', index=True, readonly=True)
    file_type = fields.Char('Type', readonly=True)
    state = fields.Selection([('running', 'En cours'), ('done', 'Terminé'), ('failed', 'Interrompu')],
                             'État', default='running', required=True, readonly=True)
    done = fields.Integer('Lignes traitées', readonly=True)
    total = fields.Integer('Lignes du fichier', readonly=True)
    progress = fields.Float('Avancement (%)', compute='_compute_progress')
    label = fields.Char('Étape', readonly=True)
    result = fields.Html('Résultat', readonly=True)
    user_id = fields.Many2one('res.users', 'Par', default=lambda self: self.env.user, readonly=True)
    date_start = fields.Datetime('Début', default=fields.Datetime.now, readonly=True)
    date_end = fields.Datetime('Fin', readonly=True)

    def _compute_progress(self):
        for log in self:
            log.progress = min(100.0, 100.0 * log.done / log.total) if log.total else 0.0

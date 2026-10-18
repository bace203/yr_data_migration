# -*- coding: utf-8 -*-
import json
import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 5            # a file killed by a server time limit is taken again (it resumes where it stopped)


class YrMigrationQueue(models.Model):
    _name = 'yr.migration.queue'
    _description = 'File d\'attente des imports fastmag'
    _order = 'state_order, type_order, part, name, id'

    name = fields.Char('Fichier', required=True, readonly=True)
    attachment_id = fields.Many2one('ir.attachment', 'Fichier déposé', ondelete='set null', readonly=True)
    options = fields.Text('Options', readonly=True)
    skip_done = fields.Boolean('Ignorer si déjà importé', default=True, readonly=True)
    file_type = fields.Char('Type', readonly=True)
    type_order = fields.Integer(readonly=True)
    part = fields.Integer('Partie', readonly=True)
    state = fields.Selection([('pending', 'En attente'), ('running', 'En cours'), ('done', 'Terminé'),
                              ('skipped', 'Ignoré'), ('failed', 'Échec')], 'État', default='pending', required=True,
                             readonly=True)
    state_order = fields.Integer(compute='_compute_state_order', store=True)
    attempts = fields.Integer('Essais', readonly=True)
    message = fields.Text('Message', readonly=True)
    log_id = fields.Many2one('yr.migration.log', 'Import', readonly=True)
    progress = fields.Float('Avancement (%)', related='log_id.progress')
    label = fields.Char('Étape', related='log_id.label')
    user_id = fields.Many2one('res.users', 'Par', default=lambda self: self.env.user, readonly=True)

    @api.depends('state')
    def _compute_state_order(self):
        for item in self:
            item.state_order = {'running': 0, 'pending': 1, 'failed': 2, 'skipped': 3, 'done': 4}[item.state]

    # ── user actions ─────────────────────────────────────────────────────
    def action_retry(self):
        self.filtered(lambda i: i.state in ('failed', 'skipped')).write(
            {'state': 'pending', 'attempts': 0, 'message': False})
        self._trigger_cron()

    def action_cancel(self):
        self.filtered(lambda i: i.state in ('pending', 'failed')).attachment_id.sudo().unlink()
        self.filtered(lambda i: i.state in ('pending', 'failed')).unlink()

    @api.model
    def _trigger_cron(self):
        cron = self.env.ref('yr_data_migration.ir_cron_yr_migration_queue', raise_if_not_found=False)
        if cron:
            cron.sudo()._trigger()

    # ── background ───────────────────────────────────────────────────────
    @api.model
    def _next_item(self):
        return self.search([('state', 'in', ('running', 'pending'))], limit=1)

    @api.model
    def _cron_run(self):
        """Imports the waiting files one after the other, without anyone in front of the screen: one file per run,
        the next run is triggered at once."""
        item = self._next_item()
        if not item:
            return
        item._process()
        if self._next_item():
            self._trigger_cron()

    def _process(self):
        self.ensure_one()
        Wizard = self.env['yr.migration.import']
        if self.attempts >= MAX_ATTEMPTS:
            self.write({'state': 'failed', 'message': _('Interrompu trop de fois (limite de temps du serveur ?). '
                                                         'Relancez ou découpez le fichier.')})
            return
        self.write({'state': 'running', 'attempts': self.attempts + 1})
        Wizard._commit()
        try:
            sub = Wizard.create(dict(json.loads(self.options or '{}'), file=self.attachment_id.datas,
                                     filename=self.name))
            if not sub.file_type:
                self.write({'state': 'skipped', 'message': _('Type de fichier non reconnu.')})
            elif self.skip_done and sub._previous_log().state == 'done':
                self.write({'state': 'skipped', 'message': _('Déjà importé en entier.')})
                self.attachment_id.sudo().unlink()
            else:
                sub.with_context(yr_queue_item=self.id).action_import()
                self.write({'state': 'done', 'message': False, 'log_id': sub.log_id.id})
                self.attachment_id.sudo().unlink()
        except Exception as error:  # noqa: BLE001 - the other files go on
            if Wizard._can_commit():
                self.env.cr.rollback()
                self.env.invalidate_all()
            _logger.exception('fastmag: échec du fichier %s', self.name)
            self.write({'state': 'failed', 'message': str(error.args[0] if error.args else error)})
        Wizard._commit()

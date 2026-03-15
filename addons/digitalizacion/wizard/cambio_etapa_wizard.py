from odoo import models, fields
from odoo.exceptions import UserError

class CambioEtapaWizard(models.TransientModel):
    _name = 'digitalizacion.cambio_etapa.wizard'
    _description = 'Wizard para Cambio Masivo de Etapa'

    etapa_destino_id = fields.Many2one(
        'digitalizacion.etapa',
        string="Etapa Destino",
        required=True,
        domain=[('active', '=', True)]
    )

    def action_cambiar_etapa(self):
        """
        Cambia la etapa_id de los registros seleccionados en la vista lista (active_ids).
        """
        # Obtenemos los IDs de los registros seleccionados desde el contexto
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return

        registros = self.env['digitalizacion.registro'].browse(active_ids)
        
        # Validar si hay registros que ya están en la etapa destino
        registros_misma_etapa = registros.filtered(lambda r: r.etapa_id == self.etapa_destino_id)
        if registros_misma_etapa:
            raise UserError(
                f"Ha seleccionado registros que ya se encuentran en la etapa '{self.etapa_destino_id.name}'. "
                f"Por favor, deselecciónelos."
            )

        # Efectuamos el cambio
        for registro in registros:
            # Aprovechamos el ORM para que se detonen los onchange de limpieza (definidos en registro.py)
            # sin embargo, onchange a veces no se detona en writes directos, 
            # por lo que forzamos la limpieza de campos llamando al método manualmente si es necesario o 
            # confiamos en que el cambio masivo solo altera la etapa_id (lo más seguro en batch).
            registro.write({
                'etapa_id': self.etapa_destino_id.id
            })

        return {'type': 'ir.actions.act_window_close'}

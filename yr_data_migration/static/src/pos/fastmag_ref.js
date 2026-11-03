/** @odoo-module */
// The till search also finds an article by its « Réf. fastmag » (the « Référence interne » is the Sage X3 one).
import { ProductProduct } from "@point_of_sale/app/models/product_product";
import { patch } from "@web/core/utils/patch";

patch(ProductProduct.prototype, {
    get searchString() {
        const base = super.searchString;
        return this.yr_fastmag_code ? `${base} ${this.yr_fastmag_code}` : base;
    },
});

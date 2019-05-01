function sciswarm_unmask() {
	jQuery(".maillink").replaceWith(function() {
		let box = this.getAttribute("data-box");
		let domain = this.getAttribute("data-domain");
		let ret = document.createElement("a");
		ret.setAttribute("href", "mailto:" + box + "@" + domain);
		ret.appendChild(document.createTextNode(box + "@" + domain));
		return ret
	});
}

jQuery(document).ready(function() {
	sciswarm_unmask();

	let hide_timers = {};
	let load_timers = {};

	function sciswarm_autocomplete_load(target) {
		if (target.value.length < 1) {
			return;
		}

		let sid = "#" + target.name + "_suggest";
		let url = jQuery(target).attr('data-callback');

		if (!url) {
			return;
		}

		let arg = {value: target.value}

		jQuery.get(url, arg, function(data) {
			let sbox = jQuery(sid);
			sbox.html(data);
			sbox.find(".suggest_item").click(target,
				sciswarm_autocomplete_choose);
		});
	}

	function sciswarm_autocomplete_choose(e) {
		let value = jQuery(e.delegateTarget).attr('data-value');
		let target = e.data;

		if (hide_timers[target.id]) {
			clearTimeout(hide_timers[target.id]);
		}

		let input = jQuery(target);
		input.val(value);
		input.focus();
		sciswarm_autocomplete_load(target);
	}

	function sciswarm_autocomplete_get(e) {
		let target = e.target

		if (load_timers[target.id]) {
			clearTimeout(load_timers[target.id]);
		}

		let callback = function() {
			sciswarm_autocomplete_load(target);
		}

		load_timers[target.id] = setTimeout(callback, 300);
	}

	function sciswarm_autocomplete_show(e) {
		let sid = "#" + e.target.name + "_suggest";
		jQuery(sid).show();
	}

	function sciswarm_autocomplete_hide(e) {
		let sid = "#" + e.target.name + "_suggest";
		let tmr = setTimeout(function() {jQuery(sid).hide();}, 300);
		hide_timers[e.target.id] = tmr;
	}

	function sciswarm_reload_select(e) {
		let target = jQuery(e.target);
		let name = target.attr('data-reload-select');
		let select = jQuery(e.target.form.elements[name]);
		select.children('option[value!=""]').remove();

		if (!e.target.value) {
			return;
		}

		let url = target.attr('data-callback');
		let arg = {value: e.target.value};

		jQuery.get(url, arg, function(data) {
			let elem, text;

			for (let idx in data) {
				elem = document.createElement("option");
				elem.setAttribute("value", data[idx][0]);
				text = document.createTextNode(data[idx][1]);
				elem.appendChild(text);
				select.append(elem);
			}
		});
	}

	let doc = jQuery(document);
	doc.on("input", "input.autocomplete", sciswarm_autocomplete_get);
	doc.on("focusin", "input.autocomplete", sciswarm_autocomplete_show);
	doc.on("focusout", "input.autocomplete", sciswarm_autocomplete_hide);
	doc.on("change", "select[data-reload-select]", sciswarm_reload_select);
})

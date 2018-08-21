function sciswarm_unmask() {
	jQuery(".maillink").replaceWith(function() {
		box = this.getAttribute("data-box");
		domain = this.getAttribute("data-domain");
		ret = document.createElement("a");
		ret.setAttribute("href", "mailto:" + box + "@" + domain);
		ret.appendChild(document.createTextNode(box + "@" + domain));
		return ret
	});
}

jQuery(document).ready(function() {
	sciswarm_unmask();

	hide_timers = {};
	load_timers = {};

	function sciswarm_autocomplete_load(target) {
		if (target.value.length < 1) {
			return;
		}
		sid = "#" + target.name + "_suggest";
		url = jQuery(target).attr('data-callback');
		if (!url) {
			return;
		}
		arg = {value: target.value}
		jQuery.get(url, arg, function(data) {
			sbox = jQuery(sid);
			sbox.html(data);
			sbox.find(".suggest_item").click(target,
				sciswarm_autocomplete_choose);
		});
	}

	function sciswarm_autocomplete_choose(e) {
		value = jQuery(e.delegateTarget).attr('data-value');
		target = e.data;
		if (hide_timers[target.id]) {
			clearTimeout(hide_timers[target.id]);
		}
		input = jQuery(target);
		input.val(value);
		input.focus();
		sciswarm_autocomplete_load(target);
	}

	function sciswarm_autocomplete_get(e) {
		target = e.target
		if (load_timers[target.id]) {
			clearTimeout(load_timers[target.id]);
		}
		callback = function() {
			sciswarm_autocomplete_load(target);
		}
		load_timers[target.id] = setTimeout(callback, 300);
	}

	function sciswarm_autocomplete_show(e) {
		sid = "#" + e.target.name + "_suggest";
		jQuery(sid).show();
	}

	function sciswarm_autocomplete_hide(e) {
		sid = "#" + e.target.name + "_suggest";
		tmr = setTimeout(function() {jQuery(sid).hide();}, 300);
		hide_timers[e.target.id] = tmr;
	}

	doc = jQuery(document);
	doc.on("input", "input.autocomplete", sciswarm_autocomplete_get);
	doc.on("focusin", "input.autocomplete", sciswarm_autocomplete_show);
	doc.on("focusout", "input.autocomplete", sciswarm_autocomplete_hide);
})

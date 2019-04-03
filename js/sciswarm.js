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
})

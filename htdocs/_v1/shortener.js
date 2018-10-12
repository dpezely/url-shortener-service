// shortener.js

function process_query_strings() {
    var qs = document.URL.match(/\?([^#]+)/);
    var request = null;
    if (qs) {
	var query_strings = qs[1].match(/([^&]+)/g);
	if (query_strings.length>0) {
	    //Log("query_strings=",query_strings);
	    for (var i=0; i!=query_strings.length; ++i) {
		//Log("query_strings",i,query_strings[i]);
		var pair = query_strings[i].match(/^([^=]+)=(.*)$/);
		if (!pair) continue;
		var param=pair[1];
		var value=pair[2];
		if (param=='short-url')
                    insert_anchor_by_id('short-url', value);
		if (param=='full-url')
                    insert_anchor_by_id('full-url', value);
	    }
	}
    }
    this.handleRequest(request);
    return request;
}

function insert_anchor_by_id(id, value) {
    var node = document.getElementById(id);
    if (node) {
        node.setAttribute('href', 'http://' + value);
        node.innerText = value;
    }
}

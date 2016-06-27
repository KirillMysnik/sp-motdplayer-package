var MOTDPlayer = function (serverId, pluginId, pageId, steamid, authToken, sessionId) {
    var motdPlayer = this;

    var ajaxPostJson = function (url, data, successCallback, errorCallback) {
        var xmlhttp = new XMLHttpRequest();

        xmlhttp.onreadystatechange=function() {
            if (xmlhttp.readyState==4)
                if (xmlhttp.status==200)
                    successCallback(JSON.parse(xmlhttp.responseText));
                else
                    errorCallback();
        }

        xmlhttp.open("POST", url, true);
        xmlhttp.setRequestHeader("Content-type", "application/json;charset=UTF-8");
        xmlhttp.setRequestHeader("X-CSRFToken", CSRF_TOKEN);
        xmlhttp.send(JSON.stringify(data, null, '\t'));
    }

    var loadingScreenNode;
    var authMethod = +/\/[\w\-]+\/\w+\/[\w\-]+\/\d+\/(1|2)\/\w+\/\d+\//g.exec(location.href)[1];
    this.post = function (data, successCallback, errorCallback) {
        ajaxPostJson("/" + serverId + "/" + pluginId + "/" + pageId + "/" + steamid + "/" + authMethod + "/" + authToken + "/" + sessionId + "/",
            {
                action: "receive-custom-data",
                custom_data: data
            }, function (response) {
                if (response['status'] == "OK") {
                    authMethod = 2;
                    authToken = response['web_auth_token'];

                    if (loadingScreenNode) {
                        loadingScreenNode.parentNode.removeChild(loadingScreenNode);
                        loadingScreenNode = null;
                    }

                    successCallback(response['custom_data']);
                }
                else
                    if (errorCallback)
                        errorCallback(response['status']);
            }, function () {
                if (errorCallback)
                    errorCallback("ERROR_AJAX_FAILURE");
            }
        );
        if (!loadingScreenNode) {
            loadingScreenNode = document.getElementsByTagName('body')[0].appendChild(document.createElement('div'));
            loadingScreenNode.classList.add('motdplayer-ajax-loading-screen');
        }
    }

    this.retarget = function (newPageId, successCallback, errorCallback) {
        ajaxPostJson("/json/retarget/" + serverId + "/" + pluginId + "/" + newPageId + "/" + pageId + "/" + steamid + "/" + authMethod + "/" + authToken + "/" + sessionId + "/",
            {
                action: "retarget",
            }, function (response) {
                if (response['status'] == "OK") {
                    authMethod = 2;
                    authToken = response['web_auth_token'];
                    pageId = newPageId;

                    if (loadingScreenNode) {
                        loadingScreenNode.parentNode.removeChild(loadingScreenNode);
                        loadingScreenNode = null;
                    }

                    successCallback();
                }
                else
                    if (errorCallback)
                        errorCallback(response['status']);
            }, function () {
                if (errorCallback)
                    errorCallback("ERROR_AJAX_FAILURE");
            }
        );
        if (!loadingScreenNode) {
            loadingScreenNode = document.getElementsByTagName('body')[0].appendChild(document.createElement('div'));
            loadingScreenNode.classList.add('motdplayer-ajax-loading-screen');
        }
    }

    this.goto = function (newPageId, args) {
        motdPlayer.retarget(newPageId, function () {
            var url = "/" + serverId + "/" + pluginId + "/" + newPageId + "/" + steamid + "/" + authMethod + "/" + authToken + "/" + sessionId + "/";
            if (args)
                url += "?" + args;
            location.href = url;
        }, function (error) {
            alert(error);
        });
    }

    document.addEventListener('DOMContentLoaded', function (e) {
        var links = document.getElementsByTagName('a');
        for (var i=0; i<links.length; i++) {
            (function (link) {
                if (link.getAttribute('data-motdplayer-goto')) {
                    link.href = "#";
                    link.addEventListener('click', function (e) {
                        motdPlayer.goto(
                            link.getAttribute('data-motdplayer-goto'),
                            link.getAttribute('data-motdplayer-args')
                        );
                    });
                }
            })(links[i]);
        }
    });
}

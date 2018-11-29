import { DataSet, Network } from 'vis/index-network';
import 'vis/dist/vis-network.min.css';

var nodes, edges, data, options, network;

const createNodesFromBackend = async() => {
  const response = await fetch('./nodes');
  const json = response.json();
  json.then(values => values.forEach(element => {
    addVisNode(element);
  }));
}

const createEdgesFromBackend = async() => {
  const response = await fetch('./connections');
  const json = response.json();
  json.then(values => values.forEach(element => {
    addVisConnection(element);
  }));
}

function addVisNode(node) {
  var uid = node["py/state"]["uid"];
  var name = node["py/state"]["effect"]["py/object"];
  nodes.add({id: uid, label: name, shape: 'box'});
}

function updateVisNode(node, json) {
  console.log(json["py/state"]);
  var uid = json["py/state"]["uid"];
  var name = json["py/state"]["effect"]["py/object"];
  node.id = uid;
  node.label = name;
  node.shape = 'box';
}

function addVisConnection(con) {
  var state = con["py/state"];
  edges.add({from: state["from_node_uid"], from_channel: state["from_node_channel"], to: state["to_node_uid"], to_channel: state["to_node_channel"], arrows:'to'});
}

function createNetwork() {
  // create an array with nodes
  nodes = new DataSet();

  // create an array with edges
  edges = new DataSet();

  // create a network
  var container = document.getElementById('network');
  data = {
    nodes: nodes,
    edges: edges
  };
  options = {
    interaction: {
      navigationButtons: false,
      hover:true
    },
    manipulation: {
      enabled: true,
      addNode: function (data, callback) {
        // filling in the popup DOM elements
        document.getElementById('node-operation').innerHTML = "Add Node";
        editNode(data, clearNodePopUp, callback);
      },
      deleteNode: function(data, callback) {
        data.nodes.forEach(id => {
          deleteNodeData(id, callback);
        });
        console.log("deleted");
        callback(data);
        
      },
      addEdge: function (data, callback) {
        if (data.from == data.to) {
          var r = confirm("Do you want to connect the node to itself?");
          if (r != true) {
            callback(null);
            return;
          }
        }
        document.getElementById('edge-operation').innerHTML = "Add Edge";
        editEdgeWithoutDrag(data, callback);
      },
    }
  };
  network = new Network(container, data, options);
  network.on("selectNode", function (params) {
    showNodeInfo(params.nodes[0]);
  });
  network.on("deselectNode", function () {
    hideNodeInfo();
  });
}

function showNodeInfo(uid) {
  document.getElementById('infoPanel').style.display = 'block';
  const fetchAndShow = async () => {
    const response = await fetch('./node/'+uid);
    const json = response.json();
    json.then(values => { 
      var effect = values["py/state"]["effect"];
      document.getElementById('infoPanel').innerHTML = '<h2>Node Info:</h2>' + JSON.stringify(effect, null, 4);
    }) ;
  }
  fetchAndShow();
}

function hideNodeInfo() {
  document.getElementById('infoPanel').style.display = 'none';
}

function editNode(data, cancelAction, callback) {
  var list1 = document.getElementById('node-effectDropdown');
  var i;
  for(i = list1.options.length - 1 ; i >= 0 ; i--)
  {
    list1.remove(i);
  }
  const fetchEffects = async() => {
    const response = await fetch('./effects');
    const json = response.json();
    json.then(values => {
      values.forEach(element => {
        console.log(element);
        list1.add(new Option(element["py/type"]))
      })
    })
  }
  fetchEffects();

  document.getElementById('node-label').value = data.label;
  document.getElementById('node-saveButton').onclick = saveNodeData.bind(this, data, callback);
  document.getElementById('node-cancelButton').onclick = cancelAction.bind(this, callback);
  document.getElementById('node-popUp').style.display = 'block';
}

async function saveNodeData(data, callback) {
  // gather data
  var effectDropdown = document.getElementById('node-effectDropdown')
  var selectedEffect = effectDropdown.options[effectDropdown.selectedIndex].value;

  // Save node in backend
  var createdNode = await fetch('./node', {
    method: 'POST', // or 'PUT'
    body: JSON.stringify(selectedEffect), // data can be `string` or {object}!
    headers:{
      'Content-Type': 'application/json'
    }
  }).then(res => res.json())
  .then(node => {
    console.log('Success:', JSON.stringify(node));
    updateVisNode(data, node);
    callback(data);
  })
  .catch(error => {
    console.error('Error:', error);
  })
  .finally(() => {
    clearNodePopUp();
  });
}

async function deleteNodeData(id) {
  var deleteNode = await fetch('./node/'+id, {
    method: 'DELETE'
  }).then(res => {
    console.log('Success');
  }).catch(error => {
    console.error('Error:', error)
  })
}

function cancelNodeEdit(callback) {
  clearNodePopUp();
  callback(null);
}

function clearNodePopUp() {
  document.getElementById('node-saveButton').onclick = null;
  document.getElementById('node-cancelButton').onclick = null;
  document.getElementById('node-popUp').style.display = 'none';
}

function editEdgeWithoutDrag(data, callback) {
  // filling in the popup DOM elements
  document.getElementById('edge-label').value = data.label;
  document.getElementById('edge-saveButton').onclick = saveEdgeData.bind(this, data, callback);
  document.getElementById('edge-cancelButton').onclick = cancelEdgeEdit.bind(this,callback);
  document.getElementById('edge-popUp').style.display = 'block';
}

function clearEdgePopUp() {
  document.getElementById('edge-saveButton').onclick = null;
  document.getElementById('edge-cancelButton').onclick = null;
  document.getElementById('edge-popUp').style.display = 'none';
}
function cancelEdgeEdit(callback) {
  clearEdgePopUp();
  callback(null);
}
function saveEdgeData(data, callback) {
  if (typeof data.to === 'object')
    data.to = data.to.id
  if (typeof data.from === 'object')
    data.from = data.from.id
  data.label = document.getElementById('edge-label').value;
  clearEdgePopUp();
  callback(data);
}

function updateNodeArgs() {
  console.log("nodeargs")
}

createNetwork();
createNodesFromBackend();
createEdgesFromBackend();

module.exports = {
  createNetwork: createNetwork,
  updateNodeArgs: updateNodeArgs
};
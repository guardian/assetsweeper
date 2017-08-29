var fileId = job.getData("fileId");
if(!fileId){
    throw "Could not get file ID from object";
}

var file = api.path("storage/file/VX-17").get();
if(!file){
    throw "File VX-17 did not exist";
}

var result = api.path("storage/file/VX-17/state/CLOSED").put();
if(!result){
    throw "Unable to set file state on VX-17";
}
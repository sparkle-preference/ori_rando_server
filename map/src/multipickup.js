// Multipickup ids (MU, RP, RG): CODE/id pieces joined by "/", a "/" inside a piece doubled.
// No imports, so plain node can load it.

function decompose_pickup(code, id) {
    if (code === "NO" && id === "1") {
        return [];
    }

    if (code != "MU" && code != "RP" && code != "RG") {
        return [[code, id]];
    }
    
    if (id === "") {
        return [];
    }

    let parts = [];
    let firstPiece = null;
    let part = '';
    for(let i = 0; i < id.length; ++i) {
        let c = id[i];
        if (c == '/') {
            if (i < id.length - 1 && id[i + 1] == '/') {
                part += '/';
                ++i;
            } else {
                if (firstPiece === null) {
                    firstPiece = part;
                    part = '';
                } else {
                    parts.push([firstPiece, part]);
                    firstPiece = null;
                    part = '';
                }
            }
        } else {
            part += c;
        }
    }
    // an odd trailing piece is dropped, as the client does
    if (firstPiece !== null) {
        parts.push([firstPiece, part]);
    }
    return parts;
}

// one CODE|id piece as a multipickup holds it; a leading "/" in the id gets a space, or its "//" would read as part of the code
const pack_piece = (piece) => piece.replace(/^([^|]*)\|\//, "$1| /").replaceAll("/", "//").replace(/\|/g, "/")

export {decompose_pickup, pack_piece};



//verify the token 
const checkAuthorized=async function(req,res,next){
    const  authHeaders=req.headers.authorization || req.headers.Authorization
    console.log(authHeaders)
    try{
        if(authHeaders===Buffer.from(process.env.Authorization).toString('base64')){
            next()
        }
        else{
           return  res.status(403).json({ error: 'Forbidden: Invalid Authorization header' })
        }}
    catch(err){
        console.log(err)
        return  res.status(403).json({ error: 'Forbidden: Invalid Authorization header' })
    }
}

module.exports={
    checkAuthorized
}

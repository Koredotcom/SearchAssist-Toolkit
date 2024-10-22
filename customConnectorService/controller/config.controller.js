const { readConfig }=require('../utils/readConfig')

const get_config_controller=async(req,res)=>{
    try {
        const config= await readConfig()
        // delete config?.authDetails
        res.json(config)

      } catch (parseError) {
        // JSON parse error
        res.status(500).json({ error: 'Error parsing JSON data' });
      }
};




module.exports={get_config_controller}
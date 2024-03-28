import React, { useState } from "react";
import axios from "axios";

const Formulaire = () => {
    const [modele, setModele] = useState("");
    const [marque, setMarque] = useState("");
    const [soustitre, setSoustitre] = useState("");
    const [prix, setPrix] = useState("");
    const [motorisation, setMotorisation] = useState("");
    const [carburant, setCarburant] = useState("");
    const [annee, setAnnee] = useState("");
    const [kms, setKms] = useState("");
    const [options, setOptions] = useState("");
    const [classification, setClassification] = useState(null);

    const handleSubmit = (e) => {
      e.preventDefault();
  
      const data = {
        modele,
        marque,
        soustitre,
        prix,
        motorisation,
        carburant,
        annee,
        kms,
        options
      };
  
      axios.post("http://localhost:3030/api/formulaire", data)
        .then((response) => {
            setClassification(response.data.result);
            console.log(response.data.result);
        })
        .catch((error) => {
            console.error(error);
        });
    };
  
    return (
      <form onSubmit={handleSubmit}>
        <input type="text" name="marque" value={marque} onChange={(e) => setMarque(e.target.value)} />
        <input type="text" name="modele" value={modele} onChange={(e) => setModele(e.target.value)} />
        <input type="text" name="soustitre" value={soustitre} onChange={(e) => setSoustitre(e.target.value)} />
        <input type="text" name="prix" value={prix} onChange={(e) => setPrix(e.target.value)} />
        <input type="text" name="motorisation" value={motorisation} onChange={(e) => setMotorisation(e.target.value)} />
        <input type="text" name="carburant" value={carburant} onChange={(e) => setCarburant(e.target.value)} />
        <input type="text" name="annee" value={annee} onChange={(e) => setAnnee(e.target.value)} />
        <input type="text" name="kms" value={kms} onChange={(e) => setKms(e.target.value)} />
        <input type="text" name="options" value={options} onChange={(e) => setOptions(e.target.value)} />
        <button type="submit">Envoyer</button>
        <div>{classification}</div>
      </form>
    );
  };
  
  export default Formulaire;
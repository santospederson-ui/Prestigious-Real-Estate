console.log(
"Prestigious Real Estate Website Loaded"
);



const track = document.querySelector(".property-track");

const next = document.querySelector(".next");

const prev = document.querySelector(".prev");


let position = 0;



if(track){


next.addEventListener("click",()=>{


position -= 380;


if(position < -760){

position = 0;

}


track.style.transform =
`translateX(${position}px)`;


});





prev.addEventListener("click",()=>{


position += 380;


if(position > 0){

position = -760;

}


track.style.transform =
`translateX(${position}px)`;


});





// automatic movement


setInterval(()=>{


next.click();


},4000);



}
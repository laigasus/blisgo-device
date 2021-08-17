// querySelector로 상수선언 
const video = document.querySelector('video');
const canvas = window.canvas = document.querySelector('canvas');
const button = document.querySelector('button');
// const downloada = document.querySelector('#downloada');

//비디오의 크기를 가져온다.
//비디오를 스크린샷 찍으면 canvas로 보여집니다.

//style="max-height: 65vh;"
//버튼을 클릭했을때 작동하는 함수입니다.
//video에 이미지정보가 canvas에 base64형태로 전달되고 그 값이 textArea에 입력됩니다.
button.onclick = function() {
  canvas.getContext('2d').drawImage(video, 0, 0, canvas.width, canvas.height);
  textArea.value = canvas.toDataURL();
  video.style.display='none';
  canvas.style.display='inline';
};

//stream 정보를 가져올떄 조건을 정해줍니다.
const constraints = {
  audio: false,
  video: {
    width: { min:640},
    height: { min:480}
  }
};

// a태그의 href 값을 바꿔서 원하는 파일이 저장되도록 설정
// downloada.onclick = function() {
//   downloada.setAttribute('href',canvas.toDataURL());
//   document.getElementById('textArea2').innerHTML = newfilename;
// }


//스트림 정보를 video태그에 전달
function handleSuccess(stream) {
  window.stream = stream; 
  video.srcObject = stream;
}
// 전달시 에러를 처리
function handleError(error) {
  console.log('navigator.MediaDevices.getUserMedia error: ', error.message, error.name);
  alert('카메라 접근이 거절되었습니다. 설정에서 승인 가능합니다.: '+error.message+error.name);
}
// getUserMedia를 통해 디바이스캠의 스트림정보를 받아옴
navigator.mediaDevices.getUserMedia(constraints)
.then(handleSuccess)
.catch(handleError);

